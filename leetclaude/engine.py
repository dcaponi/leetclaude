"""Tickets: the gate, exchanges, submissions, quiz answers, bail-outs."""
from __future__ import annotations

import hashlib
import json
import threading

from .common import EXCHANGE, CACHE_DIR, brand, detect_agent, load_config, locked_state, now, read_state
from . import bank, live, runners, sqlrun, stats
from .detect import detect

RANK = {"quiz": 0, "easy": 1, "medium": 2, "hard": 3}


class GateError(Exception):
    pass


# ---------------------------------------------------------------- items
def _item(p: dict, tier: str, lang: str) -> dict:
    if "q" in p:  # quiz
        return {"pid": f"quiz:{p['id']}", "title": "Quiz", "tier": "quiz", "kind": "quiz", "source": "bank",
                "lang": lang, "status": "pending", "attempts": 0}
    return {"pid": p["pid"], "title": p["title"], "tier": tier, "kind": p["kind"], "source": p["source"],
            "lang": "sql" if p["kind"] == "sql" else lang, "status": "pending", "attempts": 0, "url": p.get("url")}


def _project_quiz(q: dict, lang: str) -> dict:
    if not q.get("q") or not (q.get("choices") or q.get("accept")):
        raise GateError("quiz needs q and choices (+answer index) or accept (regex list)")
    pid = "pquiz:" + hashlib.sha1(q["q"].encode()).hexdigest()[:10]
    return {"pid": pid, "title": "Quiz: this project", "tier": "quiz", "kind": "quiz", "source": "claude",
            "lang": lang, "status": "pending", "attempts": 0, "quiz": q}


def new_items(tier: str, sql: bool, lang: str, exclude: set[str], quiz: dict | None = None, n: int = 1) -> list[dict]:
    cfg = load_config()
    out = []
    for _ in range(n):
        if tier == "quiz":
            if quiz:
                out.append(_project_quiz(quiz, lang))
                quiz = None
                continue
            q = bank.pick_quiz(lang, sql, exclude | {i["pid"] for i in out})
            if not q:
                raise GateError("quiz bank is empty")
            out.append(_item(q, "quiz", lang))
            continue
        ex = exclude | {i["pid"] for i in out}
        p = bank.pick(tier, "sql" if sql else "algo", lang, cfg, ex) or (bank.pick(tier, "algo", lang, cfg, ex) if sql else None)
        if not p:
            raise GateError(f"no {tier} problem available (offline and bank empty?)")
        out.append(_item(p, tier, lang))
    return out


def load(it: dict) -> dict | None:
    return it.get("quiz") or bank.get(it["pid"])


def _active(t: dict | None) -> dict | None:
    if not t:
        return None
    return next((i for i in t["queue"] if i["status"] == "active"), None)


def _activate(t: dict) -> dict | None:
    cur = _active(t)
    if cur:
        return cur
    for it in t["queue"]:
        if it["status"] == "pending":
            it["status"] = "active"
            it["started"] = now()
            stats.log("presented", t, it)
            return it
    return None


def _close(st: dict, t: dict, status: str) -> None:
    t["status"] = status
    t["closed_at"] = now()
    st["last_ticket"] = t
    st["ticket"] = None


# ---------------------------------------------------------------- commands
def gate(tier: str, task: str, project: str, sql: bool = False, lang: str | None = None, quiz: dict | None = None,
         agent: str | None = None):
    if tier not in RANK:
        raise GateError(f"tier must be one of {list(RANK)}")
    why = "requested"
    lk = runners.lang_key(lang)
    if lk and not runners.LANGS[lk].available():
        lk = None
    if not lk:
        lk, why = detect(project)
    st = read_state()
    exclude = {i["pid"] for i in (st.get("ticket") or {}).get("queue", [])}
    items = new_items(tier, sql, lk, exclude, quiz)
    with locked_state() as st:
        t = st.get("ticket")
        stacked = bool(t)
        if t:
            t["queue"] += items
            t["task"] = f"{t['task']} + {task}"
            if RANK[tier] > RANK[t["tier"]]:
                t["tier"] = tier
        else:
            t = {"id": st.get("next_id", 1), "created": now(), "task": task, "tier": tier, "sql": sql, "lang": lk,
                 "project": project, "queue": items, "status": "open", "task_done_at": None, "agent": agent or detect_agent()}
            st["next_id"] = t["id"] + 1
            st["ticket"] = t
            st["parked_prompt"] = None
        st["last_agent"] = t["agent"]
        it = _activate(t)
    stats.log("gate", t, None, tier=tier)
    return t, (items[0] if stacked else it), stacked, why


def submit(code: str, lang: str, full: bool) -> dict:
    st = read_state()
    t = st.get("ticket")
    it = _active(t)
    if not it or it["kind"] == "quiz":
        raise GateError("no active coding problem")
    p = load(it)
    n_ex = p.get("examples", 3)
    tests = p["tests"] if it["kind"] == "algo" else p["datasets"]
    idx = list(range(len(tests))) if full else list(range(min(n_ex, len(tests))))
    res = {"cases": [], "stdout": "", "stderr": "", "status": "ok"}
    if it["kind"] == "algo":
        lk = runners.lang_key(lang) or it["lang"]
        if not runners.LANGS[lk].supports(p["meta"]):
            raise GateError(f"{runners.LANGS[lk].label} can't run this problem's types; pick another language")
        r = runners.run(lk, p["meta"], [tests[i]["args"] for i in idx], code)
        res.update({k: r.get(k) for k in ("status", "compile_error", "stdout", "stderr", "ms", "note")})
        results = r.get("results") or {}
        names = [x["name"] for x in p["meta"]["params"]]
        for j, i in enumerate(idx):
            exp = tests[i]["expected"]
            kind, got = results.get(j, ("missing", None))
            ok = kind == "ok" and runners.compare(p.get("cmp", "exact"), got, exp)
            res["cases"].append({"i": i, "pass": ok, "hidden": i >= n_ex,
                                 "input": ", ".join(f"{a} = {json.dumps(v, separators=(',', ':'))}" for a, v in zip(names, tests[i]["args"])),
                                 "expected": exp, "got": got if kind == "ok" else None,
                                 "error": got if kind == "err" else ("did not run (crash/timeout before this test)" if kind == "missing" and r.get("results") is not None else None)})
    else:
        for i in idx:
            got = sqlrun.run_query(p["schema"], tests[i], code)
            ok, msg = sqlrun.compare_tables(got, p["expected"][i], p.get("ordered", False))
            res["cases"].append({"i": i, "pass": ok, "hidden": i >= n_ex, "error": None if ok else msg,
                                 "dataset": tests[i], "expected": p["expected"][i], "got": got if "error" not in got else None})
    # Hide details of hidden tests except the first failing one (LeetCode style).
    shown_fail = False
    for c in res["cases"]:
        if c["hidden"]:
            if not c["pass"] and not shown_fail:
                shown_fail = True
            elif c["pass"] or shown_fail:
                for k in ("input", "expected", "got", "dataset"):
                    c.pop(k, None)
    res["passed"] = sum(c["pass"] for c in res["cases"])
    res["total"] = len(res["cases"])
    res["all_passed"] = res["passed"] == res["total"] and not res.get("compile_error")
    res["solved"] = False
    with locked_state() as st:
        t = st.get("ticket")
        cur = _active(t)
        if cur and cur["pid"] == it["pid"]:
            if full:
                cur["attempts"] = cur.get("attempts", 0) + 1
                cur["lang"] = runners.lang_key(lang) or cur["lang"]
            if full and res["all_passed"]:
                cur["status"] = "solved"
                cur["solved_at"] = now()
                stats.log("solved", t, cur)
                nxt = _activate(t)
                res["solved"] = True
                res["next"] = nxt["title"] if nxt else None
                if not nxt:
                    _close(st, t, "solved")
    return res


def exchange() -> dict:
    st = read_state()
    t = st.get("ticket")
    it = _active(t)
    if not it or it["tier"] not in EXCHANGE or it["kind"] == "quiz":
        raise GateError("only an active hard or medium problem can be exchanged")
    lower = EXCHANGE[it["tier"]]
    items = new_items(lower, it["kind"] == "sql", t["lang"], {i["pid"] for i in t["queue"]}, n=2)
    with locked_state() as st:
        t = st.get("ticket")
        cur = _active(t)
        if not cur or cur["pid"] != it["pid"]:
            raise GateError("problem changed; refresh")
        cur["status"] = "exchanged"
        stats.log("exchanged", t, cur)
        k = t["queue"].index(cur)
        t["queue"][k + 1:k + 1] = items
        _activate(t)
    return {"ok": True, "tier": lower}


def _answer(it: dict, p: dict) -> dict:
    if it["kind"] == "quiz":
        ans = p["choices"][p["answer"]] if p.get("choices") else p.get("answer_text") or p.get("answer")
        return {"text": ans, "why": p.get("why", "")}
    sol = p.get("solution") or {}
    lang = "sql" if it["kind"] == "sql" else "python"
    return {"approach": p.get("approach"), "code": sol.get(lang), "lang": lang,
            "url": (p.get("url") or "") + "solutions/", "community": None}


def bail(wait: float = 0) -> dict:
    """Tap out. `wait`: seconds to block for the community answer (the CLI exits right away otherwise)."""
    with locked_state() as st:
        t = st.get("ticket")
        it = _active(t)
        if not it:
            raise GateError("nothing to bail on")
        p = load(it) or {}
        ans = _answer(it, p)
        it["status"] = "bailed"
        it["answer"] = ans
        stats.log("bailed", t, it)
        _close(st, t, "bailed")
        tid, pid = t["id"], it["pid"]
    if it["kind"] != "quiz" and p.get("slug"):
        want = "sql" if it["kind"] == "sql" else it["lang"]
        th = threading.Thread(target=_fetch_community, args=(tid, pid, p["slug"], want), daemon=True)
        th.start()
        if wait:
            th.join(wait)
    return ans


def _fetch_community(tid: int, pid: str, slug: str, lang: str) -> None:
    sol = live.community_solution(slug, lang)
    if not sol:
        return
    with locked_state() as st:
        t = st.get("last_ticket")
        if t and t["id"] == tid:
            for it in t["queue"]:
                if it["pid"] == pid and it.get("answer") is not None:
                    it["answer"]["community"] = sol


def quiz_answer(choice: int | None = None, text: str | None = None) -> dict:
    st = read_state()
    t = st.get("ticket")
    it = _active(t)
    if not it or it["kind"] != "quiz":
        raise GateError("no active quiz")
    q = load(it)
    if q.get("choices"):
        correct = choice is not None and int(choice) == int(q["answer"])
    else:
        correct = bank.check_written(q, text or "")
    extra = None if correct else new_items("quiz", t.get("sql", False), t["lang"], {i["pid"] for i in t["queue"]})
    with locked_state() as st:
        t = st.get("ticket")
        cur = _active(t)
        if not cur or cur["pid"] != it["pid"]:
            raise GateError("quiz changed; refresh")
        cur["attempts"] = 1
        cur["answer"] = _answer(cur, q)
        if correct:
            cur["status"] = "solved"
            stats.log("quiz_correct", t, cur)
            if not _activate(t):
                _close(st, t, "solved")
        else:
            cur["status"] = "missed"
            stats.log("quiz_missed", t, cur)
            k = t["queue"].index(cur)
            t["queue"][k + 1:k + 1] = extra  # the replacement question comes next, ahead of anything stacked
            _activate(t)
    return {"correct": correct, **_answer(it, q)}


def mark_done(note: str | None = None) -> dict | None:
    with locked_state() as st:
        t = st.get("ticket") or st.get("last_ticket")
        if not t:
            return None
        t["task_done_at"] = now()
        if note:
            t["task_note"] = note[:200]
        return t


def cancel(reason: str = "rage_quit") -> dict | None:
    with locked_state() as st:
        t = st.get("ticket")
        if not t:
            return None
        stats.log(reason, t, _active(t))
        _close(st, t, "cancelled")
        return t


# ---------------------------------------------------------------- views
_fetching: set[str] = set()


def _statement(p: dict) -> str | None:
    slug = p.get("slug")
    if not slug:
        return None
    path = CACHE_DIR / "lc" / f"{slug}.json"
    if path.exists():
        try:
            return live.sanitize_html(json.loads(path.read_text()).get("content") or "") or None
        except (json.JSONDecodeError, OSError):
            return None
    if slug not in _fetching:
        _fetching.add(slug)
        threading.Thread(target=lambda: live.statement(slug), daemon=True).start()
    return None


def item_view(it: dict, t: dict) -> dict:
    p = load(it) or {}
    v = {k: it.get(k) for k in ("pid", "title", "tier", "kind", "source", "status", "attempts", "started", "solved_at", "url", "lang", "answer")}
    v["can_exchange"] = it["status"] == "active" and it["tier"] in EXCHANGE and it["kind"] != "quiz"
    if it["kind"] == "quiz":
        v.update(q=p.get("q"), choices=p.get("choices"), written=not p.get("choices"), code=p.get("code"))
        return v
    v["lc"] = p.get("lc")
    v["statement"] = _statement(p)
    v["summary"] = p.get("summary")
    n_ex = p.get("examples", 3)
    if it["kind"] == "algo":
        names = [x["name"] for x in p["meta"]["params"]]
        v["examples"] = [{"input": ", ".join(f"{a} = {json.dumps(x, separators=(',', ':'))}" for a, x in zip(names, tc["args"])),
                          "expected": tc["expected"]} for tc in p["tests"][:n_ex]]
        v["n_tests"] = len(p["tests"])
        v["cmp"] = p.get("cmp", "exact")
        v["starters"] = {k: L.starter(p["meta"]) for k, L in runners.LANGS.items() if L.available() and L.supports(p["meta"])}
        v["langs"] = {k: runners.LANGS[k].label for k in v["starters"]}
    else:
        v["schema"] = p["schema"]
        v["examples"] = [{"dataset": d, "expected": e} for d, e in zip(p["datasets"][:n_ex], p["expected"][:n_ex])]
        v["n_tests"] = len(p["datasets"])
        v["ordered"] = p.get("ordered", False)
        v["starters"] = {"sql": "-- SQLite dialect (DATEDIFF/YEAR/MONTH/DATE_FORMAT/LEFT/RIGHT shims available)\nSELECT\n"}
        v["langs"] = {"sql": "SQL (SQLite)"}
    v["n_examples"] = min(n_ex, v["n_tests"])
    return v


def view() -> dict:
    st = read_state()
    t, closed = st.get("ticket"), False
    if not t:
        t, closed = st.get("last_ticket"), True
    out = {"version": st.get("version", 0), "parked": st.get("parked_prompt"), "now": now(), "ticket": None}
    agent = (t or {}).get("agent") or st.get("last_agent") or detect_agent()
    b = brand(agent)
    out["brand"] = {**b, "on": b["cmd"].format("on"), "off": b["cmd"].format("off"), "bail": b["cmd"].format("bail")}
    if not t:
        return out
    it = _active(t) if not closed else next((i for i in reversed(t["queue"]) if i["status"] in ("solved", "bailed")), None)
    out["closed"] = closed
    out["ticket"] = {k: t.get(k) for k in ("id", "task", "tier", "lang", "project", "status", "created", "closed_at", "task_done_at", "task_note", "agent")}
    out["ticket"]["queue"] = [{k: i.get(k) for k in ("title", "tier", "kind", "status")} for i in t["queue"]]
    out["item"] = item_view(it, t) if it else None
    return out


def status_line(cfg: dict) -> str:
    st = read_state()
    t = st.get("ticket")
    from .common import url
    if not t:
        return f"{brand()['name']}: no open ticket. The gate is open."
    it = _active(t) or {}
    mins = (now() - it.get("started", now())) / 60
    left = sum(i["status"] in ("active", "pending") for i in t["queue"])
    return (f"{brand(t.get('agent'))['name']} ticket #{t['id']}: {it.get('tier', '?')} \"{it.get('title', '?')}\" ({it.get('lang')}), "
            f"{mins:.0f}m in, {it.get('attempts', 0)} submits, {left} left → {url(cfg)}")
