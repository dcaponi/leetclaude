#!/usr/bin/env python3
"""Run `leetclaude check` on every solution under tests/solutions/<lang>/<slug>.<ext>.

The directory name is the language key and the file stem is the bank slug.
Prints one line per file and exits 1 if any file fails.

Usage: python3 tests/run_lang_tests.py [-j N] [FILTER ...]
  FILTER matches a language key or a slug (e.g. `rust`, `two-sum`); default is everything.
Set LEETCLAUDE_HOME to keep scratch runs out of ~/.leetclaude.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOLUTIONS = Path(__file__).resolve().parent / "solutions"
CLI = REPO / "bin" / "leetclaude"

sys.path.insert(0, str(REPO))
from leetclaude import runners  # noqa: E402


def collect(filters: list[str]) -> list[tuple[str, str, Path]]:
    out = []
    for f in sorted(SOLUTIONS.glob("*/*")):
        if not f.is_file() or f.name.startswith("."):
            continue
        lang, slug = f.parent.name, f.stem
        if filters and lang not in filters and slug not in filters:
            continue
        out.append((lang, slug, f))
    return out


def check(item: tuple[str, str, Path]) -> tuple[bool, str]:
    lang, slug, f = item
    rel = f.relative_to(SOLUTIONS)
    L = runners.LANGS.get(lang)
    if L is None:
        return False, f"FAIL {rel}: unknown language directory '{lang}'"
    if f.suffix != "." + L.ext:
        return False, f"FAIL {rel}: expected extension .{L.ext} for {lang}"
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(CLI), "check", f"bank:{slug}", lang, str(f)],
                           capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return False, f"FAIL {rel}: check timed out"
    dt = time.time() - t0
    text = (p.stdout.strip() or p.stderr.strip() or f"exit {p.returncode}").replace("\n", "\n    ")
    ok = p.returncode == 0 and p.stdout.startswith("ok ")
    return ok, f"{'ok  ' if ok else 'FAIL'} {str(rel):<45} {dt:5.1f}s" + ("" if ok else "\n    " + text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-j", "--jobs", type=int, default=4, help="parallel checks (default 4)")
    ap.add_argument("filters", nargs="*", help="language keys or slugs to run")
    a = ap.parse_args()
    items = collect(a.filters)
    if not items:
        print("no solution files matched", file=sys.stderr)
        return 1
    failed = 0
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        for ok, line in ex.map(check, items):
            print(line, flush=True)
            failed += not ok
    print(f"\n{len(items) - failed}/{len(items)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
