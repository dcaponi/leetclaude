"""Run LeetCode database problems on in-memory SQLite.

Datasets use LeetCode's exampleTestcases shape:
  {"headers": {"Employee": ["id", "salary"]}, "rows": {"Employee": [[1, 100], [2, 200]]}}
Results are {"cols": [...], "rows": [[...], ...]}.
"""
from __future__ import annotations

import datetime as _dt
import re
import sqlite3
import time


def _date(s):
    if s is None:
        return None
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _datediff(a, b):
    da, db = _date(a), _date(b)
    return None if da is None or db is None else (da - db).days


def _part(fmt):
    def f(d):
        x = _date(d)
        return None if x is None else int(x.strftime(fmt))
    return f


MYSQL_FMT = {"%Y": "%Y", "%y": "%y", "%m": "%m", "%c": "%-m", "%d": "%d", "%e": "%-d", "%H": "%H", "%i": "%M",
             "%s": "%S", "%M": "%B", "%b": "%b", "%W": "%A", "%a": "%a", "%j": "%j"}


def _date_format(d, fmt):
    if d is None or fmt is None:
        return None
    try:
        x = _dt.datetime.fromisoformat(str(d))
    except ValueError:
        return None
    return re.sub(r"%[a-zA-Z]", lambda m: x.strftime(MYSQL_FMT.get(m.group(0), m.group(0))), fmt)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    # A few MySQL-isms so LeetCode-style answers mostly work as written.
    conn.create_function("datediff", 2, _datediff, deterministic=True)
    conn.create_function("year", 1, _part("%Y"), deterministic=True)
    conn.create_function("month", 1, _part("%m"), deterministic=True)
    conn.create_function("day", 1, _part("%d"), deterministic=True)
    conn.create_function("date_format", 2, _date_format, deterministic=True)
    conn.create_function("left", 2, lambda s, n: None if s is None else str(s)[: int(n)], deterministic=True)
    conn.create_function("right", 2, lambda s, n: None if s is None else (str(s)[-int(n):] if int(n) else ""), deterministic=True)
    conn.create_function("lcase", 1, lambda s: None if s is None else str(s).lower(), deterministic=True)
    conn.create_function("ucase", 1, lambda s: None if s is None else str(s).upper(), deterministic=True)
    conn.create_function("char_length", 1, lambda s: None if s is None else len(str(s)), deterministic=True)
    return conn


def sanitize_ddl(ddl: str) -> str:
    ddl = re.sub(r"\benum\s*\([^)]*\)", "TEXT", ddl, flags=re.I)
    ddl = re.sub(r"\bunsigned\b", "", ddl, flags=re.I)
    ddl = re.sub(r"\bauto_increment\b", "", ddl, flags=re.I)
    ddl = re.sub(r"\)\s*(engine|default charset|charset)\b.*$", ")", ddl, flags=re.I | re.S)
    return ddl


def build_db(schema: list[str], dataset: dict) -> sqlite3.Connection:
    conn = connect()
    for ddl in schema:
        conn.execute(sanitize_ddl(ddl))
    for table, cols in dataset.get("headers", {}).items():
        rows = dataset.get("rows", {}).get(table, [])
        if rows:
            qcols = ", ".join(f'"{c}"' for c in cols)
            conn.executemany(f'INSERT INTO "{table}" ({qcols}) VALUES ({", ".join("?" * len(cols))})', rows)
    conn.commit()
    return conn


def _deny_attach(action, *args):
    return sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK


def run_query(schema: list[str], dataset: dict, query: str, timeout: float = 5.0) -> dict:
    q = query.strip().rstrip(";").strip()
    if not q:
        return {"error": "empty query"}
    try:
        conn = build_db(schema, dataset)
    except sqlite3.Error as e:
        return {"error": f"schema/data setup failed: {e}"}
    deadline = time.time() + timeout
    conn.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 20000)
    conn.set_authorizer(_deny_attach)
    try:
        cur = conn.execute(q)
        cols = [d[0] for d in (cur.description or [])]
        rows = [list(r) for r in cur.fetchmany(5000)]
        return {"cols": cols, "rows": rows}
    except sqlite3.Error as e:
        msg = str(e)
        if "interrupted" in msg:
            msg = "query timed out"
        return {"error": msg}
    finally:
        conn.close()


def norm_cell(v):
    if v is None:
        return None
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, (int, float)):
        f = float(v)
    else:
        s = str(v).strip()
        if s.lower() == "null":
            return None
        try:
            f = float(s)
        except ValueError:
            return s
        if not re.fullmatch(r"[-+]?\d+(\.\d+)?([eE][-+]?\d+)?", s):
            return s
    if f.is_integer() and abs(f) < 1e15:
        return str(int(f))
    return f"{round(f, 5):.5f}".rstrip("0").rstrip(".")


def compare_tables(got: dict, exp: dict, ordered: bool) -> tuple[bool, str]:
    if "error" in got:
        return False, got["error"]
    gc = [c.lower().strip("`\"' ") for c in got["cols"]]
    ec = [c.lower().strip("`\"' ") for c in exp["cols"]]
    if gc != ec:
        return False, f"columns differ: expected {exp['cols']}, got {got['cols']}"
    g = [tuple(norm_cell(v) for v in r) for r in got["rows"]]
    e = [tuple(norm_cell(v) for v in r) for r in exp["rows"]]
    if not ordered:
        key = lambda r: tuple((x is None, x or "") for x in r)
        g, e = sorted(g, key=key), sorted(e, key=key)
    if g != e:
        if len(g) != len(e):
            return False, f"expected {len(e)} rows, got {len(g)}"
        return False, "row values differ" + ("" if not ordered else " (order matters here)")
    return True, ""
