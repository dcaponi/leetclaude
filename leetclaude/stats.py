"""Outcome tracking in SQLite: what you were asked, what you solved, where you tapped out."""
from __future__ import annotations

import sqlite3
import time

from .common import STATS_DB, ensure_home

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, ts REAL, ticket INTEGER, pid TEXT, title TEXT, tier TEXT, kind TEXT,
  source TEXT, lang TEXT, event TEXT, attempts INTEGER, secs REAL, project TEXT, task TEXT
);
CREATE INDEX IF NOT EXISTS events_pid ON events(pid);
"""


def db() -> sqlite3.Connection:
    ensure_home()
    c = sqlite3.connect(STATS_DB, timeout=5)
    c.executescript(SCHEMA)
    return c


def log(event: str, ticket: dict | None = None, item: dict | None = None, **kw) -> None:
    ticket, item = ticket or {}, item or {}
    row = dict(ts=time.time(), ticket=ticket.get("id"), pid=item.get("pid"), title=item.get("title"),
               tier=item.get("tier") or ticket.get("tier"), kind=item.get("kind"), source=item.get("source"),
               lang=item.get("lang") or ticket.get("lang"), event=event, attempts=item.get("attempts"),
               secs=(time.time() - item["started"]) if item.get("started") else None,
               project=ticket.get("project"), task=ticket.get("task"))
    row.update(kw)
    with db() as c:
        c.execute(f"INSERT INTO events ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", list(row.values()))


def seen_pids(limit: int = 400) -> set[str]:
    with db() as c:
        return {r[0] for r in c.execute(
            "SELECT pid FROM events WHERE event='presented' AND pid IS NOT NULL ORDER BY ts DESC LIMIT ?", (limit,))}


def last_seen(pids: list[str]) -> dict[str, float]:
    with db() as c:
        return dict(c.execute(f"SELECT pid, MAX(ts) FROM events WHERE event='presented' AND pid IN "
                              f"({','.join('?' * len(pids))}) GROUP BY pid", pids)) if pids else {}


def summary() -> dict:
    with db() as c:
        tiers = {}
        for tier, ev, n, secs, att in c.execute(
                "SELECT tier, event, COUNT(*), AVG(secs), AVG(attempts) FROM events GROUP BY tier, event"):
            t = tiers.setdefault(tier or "?", {"presented": 0, "solved": 0, "bailed": 0, "exchanged": 0,
                                                "quiz_correct": 0, "quiz_missed": 0, "avg_solve_secs": None,
                                                "avg_attempts": None})
            if ev in t:
                t[ev] = n
            if ev == "solved":
                t["avg_solve_secs"] = round(secs, 1) if secs is not None else None
                t["avg_attempts"] = round(att, 2) if att is not None else None
        for t in tiers.values():
            done = t["solved"] + t["bailed"]
            t["solve_rate"] = round(t["solved"] / done, 3) if done else None
            t["bail_rate"] = round(t["bailed"] / done, 3) if done else None
        problems = [dict(zip(("pid", "title", "tier", "lang", "presented", "solved", "bailed", "exchanged"), r)) for r in c.execute(
            "SELECT pid, MAX(title), MAX(tier), MAX(lang), SUM(event='presented'), SUM(event='solved'), "
            "SUM(event='bailed'), SUM(event='exchanged') FROM events WHERE pid IS NOT NULL "
            "GROUP BY pid ORDER BY MAX(ts) DESC LIMIT 50")]
        totals = dict(c.execute("SELECT event, COUNT(*) FROM events GROUP BY event"))
        streak = 0
        for (ev,) in c.execute("SELECT event FROM events WHERE event IN ('solved','bailed','quiz_correct','quiz_missed') "
                               "ORDER BY ts DESC LIMIT 500"):
            if ev in ("solved", "quiz_correct"):
                streak += 1
            else:
                break
    return {"tiers": tiers, "problems": problems, "totals": totals, "streak": streak}


def text_table() -> str:
    s = summary()
    order = ["quiz", "easy", "medium", "hard"]
    lines = [f"{'tier':7} {'seen':>5} {'solved':>6} {'bailed':>6} {'swapped':>7} {'solve%':>6} {'avg time':>8}"]
    for tier in order + [t for t in s["tiers"] if t not in order]:
        t = s["tiers"].get(tier)
        if not t:
            continue
        seen = t["presented"]
        solved = t["solved"] + t["quiz_correct"]
        bailed = t["bailed"] + t["quiz_missed"]
        rate = f"{100 * solved / (solved + bailed):.0f}%" if solved + bailed else "-"
        avg = f"{t['avg_solve_secs'] / 60:.1f}m" if t["avg_solve_secs"] else "-"
        lines.append(f"{tier:7} {seen:>5} {solved:>6} {bailed:>6} {t['exchanged']:>7} {rate:>6} {avg:>8}")
    lines.append(f"current streak: {s['streak']}   rage-quits (turned off mid-ticket): {s['totals'].get('rage_quit', 0)}")
    return "\n".join(lines)
