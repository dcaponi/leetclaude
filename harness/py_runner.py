"""LeetClaude Python harness. Usage: python3 py_runner.py spec.json solution.py

Runs the user's LeetCode-style solution on each test and prints one marker line per test:
  @@LG@@<i>\t<json result>      or      @@LGE@@<i>\t<json error string>
Index -1 means the file itself failed to load.
"""
import json
import sys
import threading
import traceback
from collections import deque

MARK, MARKE = "@@LG@@", "@@LGE@@"

PRELUDE = '''
from typing import *
import collections, heapq, math, bisect, itertools, functools, string, re, random, operator
from collections import deque, defaultdict, Counter, OrderedDict
from heapq import heappush, heappop, heapify, heappushpop, nlargest, nsmallest
from functools import lru_cache, cache, reduce, cmp_to_key
from itertools import accumulate, permutations, combinations, product, chain, groupby
from math import inf, gcd, sqrt, ceil, floor, comb, factorial
from bisect import bisect_left, bisect_right, insort

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
'''


def emit(i, payload, err=False):
    sys.stdout.write("\n" + (MARKE if err else MARK) + f"{i}\t" + json.dumps(payload) + "\n")
    sys.stdout.flush()


def user_tb():
    etype, evalue, tb = sys.exc_info()
    frames = [f for f in traceback.extract_tb(tb) if f.filename == "solution.py"]
    lines = traceback.format_list(frames[-6:]) + traceback.format_exception_only(etype, evalue)
    return "".join(lines).strip()


def is_seq(t):
    return t.endswith("[]") or t.startswith("list<")


def elem(t):
    return t[:-2] if t.endswith("[]") else t[5:-1]


def main():
    spec = json.load(open(sys.argv[1]))
    src = open(sys.argv[2]).read()
    ns = {"__name__": "__lg_solution__"}
    exec(PRELUDE, ns)
    try:
        exec(compile(src, "solution.py", "exec"), ns)
    except SyntaxError as e:
        emit(-1, "".join(traceback.format_exception_only(type(e), e)).strip(), err=True)
        return
    except BaseException:
        emit(-1, user_tb(), err=True)
        return

    LN, TN = ns["ListNode"], ns["TreeNode"]
    meta = spec["meta"]
    fn = meta["name"]
    ptypes = [p["type"] for p in meta["params"]]
    rtype = meta["return"]["type"]
    oidx = (meta.get("output") or {}).get("paramindex")

    def build_list(a):
        head = None
        for v in reversed(a):
            head = LN(v, head)
        return head

    def build_tree(a):
        if not a or a[0] is None:
            return None
        root = TN(a[0])
        q, i = deque([root]), 1
        while q and i < len(a):
            node = q.popleft()
            if i < len(a) and a[i] is not None:
                node.left = TN(a[i])
                q.append(node.left)
            i += 1
            if i < len(a) and a[i] is not None:
                node.right = TN(a[i])
                q.append(node.right)
            i += 1
        return root

    def to_val(t, v):
        if v is None:
            return None
        if t == "ListNode":
            return build_list(v)
        if t == "TreeNode":
            return build_tree(v)
        if is_seq(t):
            return [to_val(elem(t), x) for x in v]
        if t == "double":
            return float(v)
        return v

    def ser_list(h):
        out, n = [], 0
        while h is not None and n < 200000:
            out.append(h.val)
            h, n = h.next, n + 1
        return out

    def ser_tree(r):
        if r is None:
            return []
        out, q = [], deque([r])
        while q and len(out) < 400000:
            node = q.popleft()
            if node is None:
                out.append(None)
                continue
            out.append(node.val)
            q.append(node.left)
            q.append(node.right)
        while out and out[-1] is None:
            out.pop()
        return out

    def from_val(t, r):
        if r is None:
            return [] if t in ("ListNode", "TreeNode") else None
        if t == "ListNode":
            return ser_list(r)
        if t == "TreeNode":
            return ser_tree(r)
        if is_seq(t):
            if isinstance(r, str) and elem(t) == "character":
                r = list(r)
            return [from_val(elem(t), x) for x in r]
        if t == "double":
            return float(r)
        if t == "boolean":
            return bool(r)
        if t in ("integer", "long") and isinstance(r, float) and r.is_integer():
            return int(r)
        return r

    def resolve():
        sol = ns.get("Solution")
        if isinstance(sol, type) and hasattr(sol, fn):
            return getattr(sol(), fn)
        if callable(ns.get(fn)):
            return ns[fn]
        raise NameError(f"no method '{fn}' found: expected `class Solution` with `def {fn}(self, ...)`")

    for i, args in enumerate(spec["tests"]):
        try:
            f = resolve()
            a = [to_val(t, x) for t, x in zip(ptypes, args)]
            r = f(*a)
            if oidx is not None:
                out = from_val(ptypes[oidx], a[oidx])
            else:
                out = from_val(rtype, r)
            json.dumps(out)  # surface unserializable results as a test error
            emit(i, out)
        except RecursionError:
            emit(i, "RecursionError: maximum recursion depth exceeded", err=True)
        except BaseException:
            emit(i, user_tb(), err=True)


if __name__ == "__main__":
    sys.setrecursionlimit(1_000_000)
    threading.stack_size(256 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()
