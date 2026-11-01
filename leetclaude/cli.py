"""leetclaude CLI. Every command prints at most a few short lines (Claude reads this output; tokens matter)."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .common import LOG_FILE, PID_FILE, REPO, brand, cmd, detect_agent, is_enabled, load_config, project_root, read_state, save_config, url


def code_rev() -> str:
    files = list((REPO / "leetclaude").glob("*.py")) + [REPO / "bank" / "bank.json"]
    return str(int(max(f.stat().st_mtime for f in files if f.exists())))


def ping(cfg) -> dict | None:
    try:
        with urllib.request.urlopen(url(cfg) + "api/ping", timeout=0.7) as r:
            return json.loads(r.read())
    except (OSError, ValueError):
        return None


def stop_server(cfg) -> bool:
    info = ping(cfg)
    pid = info and info.get("pid")
    if not pid and PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
        except ValueError:
            pid = None
    if not pid:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    for _ in range(20):
        if not ping(cfg):
            break
        time.sleep(0.1)
    return True


def ensure_server(cfg) -> dict:
    info = ping(cfg)
    if info and info.get("rev") not in (None, code_rev()):
        stop_server(cfg)
        info = None
    if info:
        return info
    log = open(LOG_FILE, "a")
    env = dict(os.environ, LEETCLAUDE_REV=code_rev(), PYTHONPATH=str(REPO))
    subprocess.Popen([sys.executable, "-m", "leetclaude.server"], cwd=str(REPO), stdout=log, stderr=log,
                     stdin=subprocess.DEVNULL, start_new_session=True, env=env)
    for _ in range(40):
        time.sleep(0.1)
        info = ping(cfg)
        if info:
            return info
    raise SystemExit(f"{brand()['name']} server failed to start; see {LOG_FILE}")


def open_browser(u: str) -> None:
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        subprocess.Popen([opener, u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def cmd_gate(a, cfg):
    from . import engine, runners
    quiz = None
    if a.quiz:
        try:
            quiz = json.loads(a.quiz)
        except json.JSONDecodeError as e:
            raise SystemExit(f"--quiz is not valid JSON: {e}")
    proj = a.project or project_root()
    try:
        t, it, stacked, why = engine.gate(a.tier, a.task, proj, sql=a.sql, lang=a.lang, quiz=quiz, agent=detect_agent())
    except engine.GateError as e:
        raise SystemExit(f"{brand()['name']}: {e}")
    info = ensure_server(cfg)
    u = url(cfg)
    if cfg.get("open_browser", True) and (info.get("last_poll_age") or 1e9) > 8:
        open_browser(u)
    lang = "SQL" if it["kind"] == "sql" else runners.LANGS[it["lang"]].label
    label = "quiz" if it["kind"] == "quiz" else f"{it['tier']} \"{it['title']}\""
    gated = "" if is_enabled(cfg, proj) else f"  (gate not enforced here: {cmd('on')})"
    print(f"{brand()['name']} #{t['id']}{' (stacked)' if stacked else ''}: {label} in {lang} → {u}{gated}")


def cmd_status(a, cfg):
    from . import engine
    proj = project_root()
    print(engine.status_line(cfg) + ("" if is_enabled(cfg, proj) else "  [gate OFF for this project]"))


def cmd_on(a, cfg):
    root = "*" if a.all else project_root()
    if root not in cfg["enabled"]:
        cfg["enabled"].append(root)
    save_config(cfg)
    print(f"{brand()['name']} ON for {'every project' if root == '*' else root}. Code tasks now cost LeetCode.")


def cmd_off(a, cfg):
    from . import engine
    root = project_root()
    if a.all:
        cfg["enabled"] = []
    else:
        cfg["enabled"] = [r for r in cfg["enabled"] if r not in (root, "*")]
    save_config(cfg)
    t = engine.cancel("rage_quit")
    note = f" Open ticket #{t['id']} cancelled (logged as a rage-quit)." if t else ""
    print(f"{brand()['name']} OFF for {'all projects' if a.all else root}.{note}")


def cmd_done(a, cfg):
    from . import engine
    t = engine.mark_done(a.note)
    print("noted" if t else "no ticket")


def cmd_bail(a, cfg):
    from . import engine
    try:
        ans = engine.bail(wait=8)  # this process exits next, so let the community-answer fetch finish
    except engine.GateError as e:
        raise SystemExit(f"{brand()['name']}: {e}")
    print("Tapped out. Gate open. Answer is on the page: " + url(cfg))


def cmd_stats(a, cfg):
    from . import stats
    print(json.dumps(stats.summary(), indent=1) if a.json else stats.text_table())


def cmd_serve(a, cfg):
    from . import server
    server.main()


def cmd_start(a, cfg):
    ensure_server(cfg)
    print(url(cfg))


def cmd_stop(a, cfg):
    print("stopped" if stop_server(cfg) else "not running")


def cmd_open(a, cfg):
    ensure_server(cfg)
    open_browser(url(cfg))
    print(url(cfg))


def cmd_config(a, cfg):
    if a.set:
        k, _, v = a.set.partition("=")
        try:
            cfg[k] = json.loads(v)
        except json.JSONDecodeError:
            cfg[k] = v
        save_config(cfg)
    print(json.dumps(cfg, indent=1))


def cmd_starter(a, cfg):
    from . import bank, runners
    p = bank.get(a.pid)
    print(runners.LANGS[runners.lang_key(a.lang)].starter(p["meta"]))


def cmd_check(a, cfg):
    """Dev: run a solution file against a problem's full tests. Exit 1 on any failure."""
    from . import bank, runners, sqlrun
    p = bank.get(a.pid)
    code = Path(a.file).read_text()
    if p["kind"] == "sql":
        bad = [i for i, (ds, exp) in enumerate(zip(p["datasets"], p["expected"]))
               if not sqlrun.compare_tables(sqlrun.run_query(p["schema"], ds, code), exp, p.get("ordered", False))[0]]
    else:
        lk = runners.lang_key(a.lang)
        r = runners.run(lk, p["meta"], [t["args"] for t in p["tests"]], code)
        if r.get("compile_error"):
            print(f"FAIL {a.pid} [{lk}] compile: {r['compile_error'][:800]}")
            raise SystemExit(1)
        res = r.get("results") or {}
        bad = [i for i, t in enumerate(p["tests"]) if res.get(i, ("x",))[0] != "ok" or not runners.compare(p.get("cmp", "exact"), res[i][1], t["expected"])]
        if bad:
            i = bad[0]
            print(f"FAIL {a.pid} [{lk}] test {i}: args={json.dumps(p['tests'][i]['args'])[:200]} expected={json.dumps(p['tests'][i]['expected'])[:200]} got={res.get(i)} stderr={(r.get('stderr') or '')[:400]}")
            raise SystemExit(1)
    if bad:
        print(f"FAIL {a.pid}: datasets {bad}")
        raise SystemExit(1)
    print(f"ok {a.pid} [{a.lang}]")


def main(argv=None):
    b = brand()
    ap = argparse.ArgumentParser(prog=b["cli"], description=f"Solve a LeetCode problem before {b['agent_name']} may proceed.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="open a ticket sized to the task")
    g.add_argument("--tier", required=True, choices=["quiz", "easy", "medium", "hard"])
    g.add_argument("--task", required=True, help="short summary of the user's request")
    g.add_argument("--sql", action="store_true", help="database task: use a SQL problem")
    g.add_argument("--lang", help="override detected language")
    g.add_argument("--quiz", help='project quiz JSON: {"q":..,"choices":[..],"answer":i,"why":..} or {"q":..,"accept":[regex],"answer":..}')
    g.add_argument("--project", help="project root (default: git toplevel of cwd)")
    g.set_defaults(fn=cmd_gate)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("on")
    p.add_argument("--all", action="store_true", help="enforce in every project")
    p.set_defaults(fn=cmd_on)
    p = sub.add_parser("off")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_off)
    p = sub.add_parser("done", help="mark the background task finished (the UI taunts accordingly)")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_done)
    sub.add_parser("bail", help="tap out of the current problem; answer appears in the UI").set_defaults(fn=cmd_bail)
    p = sub.add_parser("stats")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_stats)
    for name, fn in (("serve", cmd_serve), ("start", cmd_start), ("stop", cmd_stop), ("open", cmd_open)):
        sub.add_parser(name).set_defaults(fn=fn)
    p = sub.add_parser("config")
    p.add_argument("--set", help="key=jsonvalue, e.g. source=\"bank\" or live_ratio=0.8")
    p.set_defaults(fn=cmd_config)
    p = sub.add_parser("starter")
    p.add_argument("pid")
    p.add_argument("lang")
    p.set_defaults(fn=cmd_starter)
    p = sub.add_parser("check")
    p.add_argument("pid")
    p.add_argument("lang")
    p.add_argument("file")
    p.set_defaults(fn=cmd_check)
    a = ap.parse_args(argv)
    a.fn(a, load_config())


if __name__ == "__main__":
    main()
