#!/usr/bin/env python3
"""Build bank/bank.json from bank_src/*.py.

Expected outputs are never hand-typed in bulk: each problem ships a reference solution, and this script
runs it through the real Python harness (algo) or SQLite runner (sql) to produce `expected`. Hand-written
`check` values (usually LeetCode's own examples) are asserted against the reference to catch bugs in it.

Usage: python3 scripts/build_bank.py [--only slug,slug]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from leetclaude import runners, sqlrun  # noqa: E402

SRC = REPO / "bank_src"
OUT = REPO / "bank" / "bank.json"
TIERS = {"easy", "medium", "hard"}


def M(name, params, ret, out=None):
    m = {"name": name, "params": [{"name": n, "type": t} for n, t in params], "return": {"type": ret}}
    if out is not None:
        m["output"] = {"paramindex": out}
    return m


def D(**tables):
    """D(Person=(["id", "email"], [[1, "a@b.com"]])) -> LeetCode dataset dict."""
    return {"headers": {k: v[0] for k, v in tables.items()}, "rows": {k: v[1] for k, v in tables.items()}}


def load(name):
    ns = {"M": M, "D": D}
    path = SRC / f"{name}.py"
    if not path.exists():
        return ns
    exec(compile(path.read_text(), str(path), "exec"), ns)
    return ns


def build_algo(p):
    meta = p["meta"]
    tests = p["tests"]
    r = runners.run("python", meta, tests, p["solution"], timeout=60)
    if r.get("compile_error"):
        raise SystemExit(f"[{p['slug']}] reference failed to load:\n{r['compile_error']}")
    res = r.get("results") or {}
    out = []
    for i, args in enumerate(tests):
        kind, val = res.get(i, ("missing", None))
        if kind != "ok":
            raise SystemExit(f"[{p['slug']}] reference errored on test {i} {json.dumps(args)[:200]}: {val}")
        out.append({"args": args, "expected": val})
    for i, want in (p.get("check") or {}).items():
        got = out[i]["expected"]
        if not runners.compare(p.get("cmp", "exact"), got, want):
            raise SystemExit(f"[{p['slug']}] check failed on test {i}: reference gave {got}, expected {want}")
    return {"tests": out, "meta": meta, "cmp": p.get("cmp", "exact")}


def build_sql(p):
    exp = []
    for i, ds in enumerate(p["datasets"]):
        got = sqlrun.run_query(p["schema"], ds, p["solution"])
        if "error" in got:
            raise SystemExit(f"[{p['slug']}] reference SQL failed on dataset {i}: {got['error']}")
        exp.append(got)
    for i, want in (p.get("check") or {}).items():
        ok, msg = sqlrun.compare_tables(exp[i], want, p.get("ordered", False))
        if not ok:
            raise SystemExit(f"[{p['slug']}] check failed on dataset {i}: {msg}; reference gave {exp[i]}")
    return {"schema": p["schema"], "datasets": p["datasets"], "expected": exp, "ordered": p.get("ordered", False)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    problems, seen = [], set()
    for kind, src in (("algo", "algo"), ("sql", "sql")):
        for p in load(src).get("PROBLEMS", []):
            slug = p["slug"]
            if slug in seen:
                raise SystemExit(f"duplicate slug {slug}")
            seen.add(slug)
            if p["tier"] not in TIERS:
                raise SystemExit(f"[{slug}] bad tier {p['tier']}")
            if only and slug not in only:
                continue
            entry = {"pid": f"bank:{slug}", "slug": slug, "lc": p.get("lc"), "title": p["title"], "tier": p["tier"],
                     "kind": kind, "source": "bank", "url": f"https://leetcode.com/problems/{slug}/",
                     "summary": p.get("summary", ""), "examples": p.get("examples", 3 if kind == "algo" else 1),
                     "approach": p.get("approach", ""),
                     "solution": {"python" if kind == "algo" else "sql": p["solution"].strip("\n") + "\n"}}
            entry.update(build_algo(p) if kind == "algo" else build_sql(p))
            problems.append(entry)
            print(f"ok  {kind:4} {p['tier']:6} {slug} ({len(entry.get('tests') or entry.get('datasets'))} tests)")
    quiz = load("quiz").get("QUIZ", [])
    ids = set()
    for q in quiz:
        if q["id"] in ids:
            raise SystemExit(f"duplicate quiz id {q['id']}")
        ids.add(q["id"])
        if "choices" in q and not (0 <= q["answer"] < len(q["choices"])):
            raise SystemExit(f"quiz {q['id']}: answer index out of range")
        if "choices" not in q and not q.get("accept"):
            raise SystemExit(f"quiz {q['id']}: needs choices or accept")
    if only and OUT.exists():  # partial rebuild: merge into existing bank
        old = json.loads(OUT.read_text())
        keep = [p for p in old["problems"] if p["slug"] not in {x["slug"] for x in problems}]
        problems = keep + problems
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"problems": problems, "quiz": quiz}, indent=1))
    counts = {}
    for p in problems:
        counts[(p["kind"], p["tier"])] = counts.get((p["kind"], p["tier"]), 0) + 1
    print(f"wrote {OUT.relative_to(REPO)}: {len(problems)} problems {dict(sorted(counts.items()))}, {len(quiz)} quiz")


if __name__ == "__main__":
    main()
