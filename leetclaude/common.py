"""Paths, config, and locked JSON state shared by the CLI, server, and hook."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("LEETCLAUDE_HOME", Path.home() / ".leetclaude"))
STATE_FILE = HOME / "state.json"
CONFIG_FILE = HOME / "config.json"
LOCK_FILE = HOME / ".lock"
STATS_DB = HOME / "stats.db"
CACHE_DIR = HOME / "cache"
RUN_DIR = HOME / "runs"
LOG_FILE = HOME / "server.log"
PID_FILE = HOME / "server.pid"

TIERS = ("quiz", "easy", "medium", "hard")

# Same tool, two names: LeetClaude under Claude Code, LeetCodex under Codex.
BRANDS = {
    "claude": {"agent": "claude", "name": "LeetClaude", "agent_name": "Claude", "cli": "leetclaude", "cmd": "/leetclaude:{}"},
    "codex": {"agent": "codex", "name": "LeetCodex", "agent_name": "Codex", "cli": "leetcodex", "cmd": "$leetcodex {}"},
}


def detect_agent(env=None, argv0: str | None = None) -> str:
    """Which coding agent is driving us: an explicit override, then how we were invoked, then the agent's env vars."""
    env = os.environ if env is None else env
    forced = (env.get("LEETCLAUDE_AGENT") or "").strip().lower()
    if forced in BRANDS:
        return forced
    prog = os.path.basename(argv0 if argv0 is not None else (sys.argv[0] if sys.argv else ""))
    if prog.startswith("leetcodex"):
        return "codex"
    if prog.startswith("leetclaude"):
        if env.get("CLAUDECODE") or env.get("CLAUDE_CODE_CHILD_SESSION") or not any(k.startswith("CODEX_") for k in env):
            return "claude"
    if any(k.startswith("CODEX_") for k in env):
        return "codex"
    return "claude"


def brand(agent: str | None = None) -> dict:
    return BRANDS.get(agent or detect_agent(), BRANDS["claude"])


def cmd(sub: str, agent: str | None = None) -> str:
    """How the user runs a subcommand in their agent, e.g. `/leetclaude:off` or `$leetcodex off`."""
    return brand(agent)["cmd"].format(sub)
EXCHANGE = {"hard": "medium", "medium": "easy"}  # one of these -> two of the lower tier

DEFAULT_CONFIG = {
    "port": 4790,
    # "bank" = curated problems only, "live" = random LeetCode pulls only,
    # "mix" = live with probability live_ratio, falling back to bank on any failure.
    "source": "mix",
    "live_ratio": 0.5,
    "open_browser": True,
    "enabled": [],  # project roots where the gate is enforced; "*" = everywhere
}


def ensure_home() -> None:
    for d in (HOME, CACHE_DIR, RUN_DIR, CACHE_DIR / "lc", CACHE_DIR / "live"):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_home()
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text()))
        except json.JSONDecodeError:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    ensure_home()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    tmp.replace(CONFIG_FILE)


def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"next_id": 1, "ticket": None, "last_ticket": None, "parked_prompt": None, "version": 0}


def read_state() -> dict:
    """Unlocked read (fine for display and the hook)."""
    ensure_home()
    return _read_state()


@contextlib.contextmanager
def locked_state():
    """Read-modify-write the state file under an exclusive lock."""
    ensure_home()
    with open(LOCK_FILE, "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            st = _read_state()
            yield st
            st["version"] = st.get("version", 0) + 1
            tmp = STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(st, indent=1))
            tmp.replace(STATE_FILE)
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def project_root(cwd: str | os.PathLike | None = None) -> str:
    cwd = str(cwd or os.getcwd())
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=3)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return os.path.realpath(cwd)


def is_enabled(cfg: dict, cwd: str) -> bool:
    roots = cfg.get("enabled") or []
    if "*" in roots:
        return True
    real = os.path.realpath(cwd)
    return any(real == r or real.startswith(r.rstrip("/") + "/") for r in roots)


def now() -> float:
    return time.time()


def url(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    return f"http://127.0.0.1:{cfg['port']}/"
