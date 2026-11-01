"""Curated problem bank + quiz bank + problem resolution/selection."""
from __future__ import annotations

import functools
import json
import random
import re

from .common import REPO
from . import live, runners, stats

BANK_FILE = REPO / "bank" / "bank.json"


@functools.lru_cache(maxsize=1)
def bank() -> dict:
    if not BANK_FILE.exists():
        return {"problems": [], "quiz": []}
    return json.loads(BANK_FILE.read_text())


def problems() -> list[dict]:
    return bank()["problems"]


def quizzes() -> list[dict]:
    return bank()["quiz"]


def get(pid: str) -> dict | None:
    kind, _, key = pid.partition(":")
    if kind == "bank":
        return next((p for p in problems() if p["slug"] == key), None)
    if kind == "lc":
        return live.load_live(key)
    if kind == "quiz":
        return next((q for q in quizzes() if q["id"] == key), None)
    return None


def _prefer_fresh(cands: list[dict], key=lambda p: p["pid"]) -> dict | None:
    if not cands:
        return None
    seen = stats.last_seen([key(c) for c in cands])
    fresh = [c for c in cands if key(c) not in seen]
    if fresh:
        return random.choice(fresh)
    return min(cands, key=lambda c: seen.get(key(c), 0))


def pick_bank(tier: str, kind: str, lang: str, exclude: set[str]) -> dict | None:
    L = runners.LANGS[lang]
    cands = [p for p in problems() if p["tier"] == tier and p["kind"] == kind and p["pid"] not in exclude
             and (kind == "sql" or L.supports(p["meta"]))]
    return _prefer_fresh(cands)


def pick_quiz(lang: str, sql: bool, exclude: set[str]) -> dict | None:
    want = {lang, "general", "git", "http", "testing", "design"} | ({"sql"} if sql else set())
    cands = [q for q in quizzes() if f"quiz:{q['id']}" not in exclude and set(q.get("tags", ["general"])) & want]
    q = _prefer_fresh(cands or [q for q in quizzes() if f"quiz:{q['id']}" not in exclude], key=lambda q: f"quiz:{q['id']}")
    return q


def pick(tier: str, kind: str, lang: str, cfg: dict, exclude: set[str]) -> dict | None:
    """Pick a problem: live LeetCode random pull and/or curated bank, per config, with fallback."""
    src = cfg.get("source", "mix")
    live_first = src == "live" or (src == "mix" and random.random() < float(cfg.get("live_ratio", 0.5)))
    order = ["live", "bank"] if live_first else ["bank", "live"]
    if src == "bank":
        order = ["bank"]
    seen = stats.seen_pids() | exclude
    L = runners.LANGS[lang]
    for s in order:
        if s == "live":
            p = live.random_problem(tier, kind, seen, ok=lambda p: kind == "sql" or L.supports(p["meta"]))
        else:
            p = pick_bank(tier, kind, lang, exclude)
        if p:
            return p
    return None


def check_written(q: dict, text: str) -> bool:
    t = (text or "").strip().lower()
    return bool(t) and any(re.search(rx, t, re.I) for rx in q.get("accept", []))
