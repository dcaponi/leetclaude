"""Per-language starters, harness generation, execution, and result comparison.

Problems use LeetCode's own metaData shape:
  {"name": "twoSum", "params": [{"name": "nums", "type": "integer[]"}, ...],
   "return": {"type": "integer[]"}, "output": {"paramindex": 0}}   # output only for in-place problems
Supported types: integer long double boolean string character ListNode TreeNode, plus X[] / list<X> nesting.
Test values are JSON: ListNode = array, TreeNode = LeetCode level order with nulls, character = 1-char string.
"""
from __future__ import annotations

import fcntl
import functools
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .common import REPO, RUN_DIR, ensure_home

MARK, MARKE = "@@LG@@", "@@LGE@@"
SCALARS = ("integer", "long", "double", "boolean", "string", "character")
NODES = ("ListNode", "TreeNode")
HARNESS = REPO / "harness"


# ---------------------------------------------------------------- type helpers
def is_seq(t: str) -> bool:
    return t.endswith("[]") or (t.startswith("list<") and t.endswith(">"))


def is_list(t: str) -> bool:
    return t.startswith("list<")


def elem(t: str) -> str:
    return t[:-2] if t.endswith("[]") else t[5:-1]


def base(t: str) -> str:
    while is_seq(t):
        t = elem(t)
    return t


def norm(t: str) -> str:
    """list<X> -> X[] (for languages where they are the same thing)."""
    return norm(elem(t)) + "[]" if is_seq(t) else t


def all_types(meta: dict) -> list[str]:
    return [p["type"] for p in meta["params"]] + [meta["return"]["type"]]


def uses(meta: dict, name: str) -> bool:
    return any(base(t) == name for t in all_types(meta))


def meta_supported(meta: dict) -> bool:
    ok = all(base(t) in SCALARS + NODES for t in [p["type"] for p in meta["params"]])
    rt = meta["return"]["type"]
    if rt == "void":
        return ok and (meta.get("output") or {}).get("paramindex") is not None
    return ok and base(rt) in SCALARS + NODES


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def pascal(name: str) -> str:
    return name[:1].upper() + name[1:]


def strip_comments(code: str, style: str = "c") -> str:
    if style == "c":
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
        return re.sub(r"//[^\n]*", "", code)
    return re.sub(r"#[^\n]*", "", code)


def defines(code: str, pattern: str, style: str = "c") -> bool:
    return re.search(pattern, strip_comments(code, style)) is not None


def cstr(s: str, ctrl=lambda c: "\\%03o" % ord(c)) -> str:
    out = ['"']
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20:
            out.append(ctrl(ch))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def cchar(c: str) -> str:
    return {"'": "'\\''", "\\": "'\\\\'", "\n": "'\\n'", "\t": "'\\t'"}.get(c, f"'{c}'")


def dlit(v) -> str:
    s = repr(float(v))
    if s in ("inf", "-inf", "nan"):
        raise ValueError("non-finite double in test")
    return s


# ---------------------------------------------------------------- language table
class Lang:
    key = ""
    label = ""
    ext = ""
    tools: tuple[str, ...] = ()
    leetcode_slug = ""  # LeetCode solution-article tag

    def available(self) -> bool:
        return all(shutil.which(t) for t in self.tools)

    def starter(self, meta: dict) -> str:
        raise NotImplementedError

    def prepare(self, work: Path, meta: dict, tests: list, code: str):
        """Write files into work; return (build_cmd or None, run_cmd)."""
        raise NotImplementedError

    def supports(self, meta: dict) -> bool:
        return meta_supported(meta)

    def typecheck(self, work: Path, code: str):
        """Optional static check that runs alongside the tests.
        Return (cmd, cwd, note): cmd is None to skip; note (or None) goes into run()'s result."""
        return None, None, None

    def typecheck_result(self, rc: int, out: str):
        """(compile_error text or None, note or None) from the typecheck output."""
        return None, None


def defs_comment(meta: dict, prefix: str, listdef: list[str], treedef: list[str]) -> str:
    mark = prefix.strip()

    def pre(l):
        return l if l.lstrip().startswith(mark) else prefix + l
    out = []
    if uses(meta, "ListNode"):
        out += [f"{prefix}Definition for singly-linked list."] + [pre(l) for l in listdef]
    if uses(meta, "TreeNode"):
        out += [f"{prefix}Definition for a binary tree node."] + [pre(l) for l in treedef]
    return "\n".join(out)


# ---------- Python
class Python(Lang):
    key, label, ext, tools, leetcode_slug = "python", "Python 3", "py", ("python3",), "python3"

    def ptype(self, t):
        if t in ("integer", "long"):
            return "int"
        if t == "double":
            return "float"
        if t == "boolean":
            return "bool"
        if t in ("string", "character"):
            return "str"
        if t in NODES:
            return f"Optional[{t}]"
        if t == "void":
            return "None"
        return f"List[{self.ptype(elem(t))}]"

    def starter(self, meta):
        hdr = defs_comment(meta, "# ",
                           ["class ListNode:", "    def __init__(self, val=0, next=None):",
                            "        self.val = val", "        self.next = next"],
                           ["class TreeNode:", "    def __init__(self, val=0, left=None, right=None):",
                            "        self.val = val", "        self.left = left", "        self.right = right"])
        params = ", ".join(f"{p['name']}: {self.ptype(p['type'])}" for p in meta["params"])
        sig = f"    def {meta['name']}(self, {params}) -> {self.ptype(meta['return']['type'])}:"
        body = "        " + ("# Do not return anything, modify the input in-place." if meta["return"]["type"] == "void" else "")
        return (hdr + "\n" if hdr else "") + f"class Solution:\n{sig}\n{body}\n        pass\n"

    def prepare(self, work, meta, tests, code):
        (work / "spec.json").write_text(json.dumps({"meta": meta, "tests": tests}))
        (work / "solution.py").write_text(code)
        return None, [sys.executable or "python3", "-I", str(HARNESS / "py_runner.py"), "spec.json", "solution.py"]


# ---------- Ruby
class Ruby(Lang):
    key, label, ext, tools, leetcode_slug = "ruby", "Ruby", "rb", ("ruby",), "ruby"

    def rtype(self, t):
        if t in ("integer", "long"):
            return "Integer"
        if t == "double":
            return "Float"
        if t == "boolean":
            return "Boolean"
        if t in ("string", "character"):
            return "String"
        if t in NODES:
            return t
        if t == "void":
            return "Void"
        return self.rtype(elem(t)) + "[]"

    def starter(self, meta):
        hdr = defs_comment(meta, "# ",
                           ["class ListNode", "#     attr_accessor :val, :next", "#     def initialize(val = 0, _next = nil)", "# end"],
                           ["class TreeNode", "#     attr_accessor :val, :left, :right", "#     def initialize(val = 0, left = nil, right = nil)", "# end"])
        lines = [hdr] if hdr else []
        lines += [f"# @param {{{self.rtype(p['type'])}}} {snake(p['name'])}" for p in meta["params"]]
        lines.append(f"# @return {{{self.rtype(meta['return']['type'])}}}")
        args = ", ".join(snake(p["name"]) for p in meta["params"])
        lines += [f"def {snake(meta['name'])}({args})", "    ", "end", ""]
        return "\n".join(lines)

    def prepare(self, work, meta, tests, code):
        (work / "spec.json").write_text(json.dumps({"meta": meta, "tests": tests, "rb_name": snake(meta["name"])}))
        (work / "solution.rb").write_text(code)
        return None, ["ruby", str(HARNESS / "runner.rb"), "spec.json", "solution.rb"]


# ---------- JavaScript / TypeScript
JS_DEFS = {
    "ListNode": "function ListNode(val, next) { this.val = (val === undefined ? 0 : val); this.next = (next === undefined ? null : next); }",
    "TreeNode": "function TreeNode(val, left, right) { this.val = (val === undefined ? 0 : val); this.left = (left === undefined ? null : left); this.right = (right === undefined ? null : right); }",
}

# Written as lg_main.js; loads the user's file (with the shim from harness_src) so that syntax and
# load errors are caught and reported as index -1 (compile_error), like the Python and Ruby harnesses.
JS_MAIN = r"""
;(function __lgMain() {
  const fs = require('fs'), path = require('path');
  const M = "@@LG@@", ME = "@@LGE@@";
  const emit = (i, v, err) => fs.writeSync(1, "\n" + (err ? ME : M) + i + "\t" + JSON.stringify(v) + "\n");
  // Message (incl. Node's code frame for syntax errors) + the user's own stack frames.
  const short = e => {
    if (!(e instanceof Error)) return String(e);
    const lines = String(e.stack || e).split("\n");
    let k = lines.findIndex(l => /^\s+at /.test(l));
    if (k < 0) k = lines.length;
    return lines.slice(0, k).concat(lines.slice(k).filter(l => l.includes("solution.")).slice(0, 6)).join("\n").trim();
  };
  let H;
  try { require(path.resolve(process.argv[2])); H = globalThis.__lg; }
  catch (e) { emit(-1, short(e), true); return; }
  const spec = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const meta = spec.meta, ptypes = meta.params.map(p => p.type), rtype = meta.return.type;
  const oidx = meta.output ? meta.output.paramindex : undefined;
  const isSeq = t => t.endsWith("[]") || t.startsWith("list<");
  const elem = t => t.endsWith("[]") ? t.slice(0, -2) : t.slice(5, -1);
  const LN = H.LN, TN = H.TN;
  const buildList = a => { let h = null; for (let i = a.length - 1; i >= 0; i--) h = new LN(a[i], h); return h; };
  const buildTree = a => {
    if (!a.length || a[0] === null) return null;
    const root = new TN(a[0]); const q = [root]; let i = 1, qi = 0;
    while (qi < q.length && i < a.length) {
      const n = q[qi++];
      if (i < a.length && a[i] !== null) { n.left = new TN(a[i]); q.push(n.left); } i++;
      if (i < a.length && a[i] !== null) { n.right = new TN(a[i]); q.push(n.right); } i++;
    }
    return root;
  };
  const to = (t, v) => v === null ? null : t === "ListNode" ? buildList(v) : t === "TreeNode" ? buildTree(v)
    : isSeq(t) ? v.map(x => to(elem(t), x)) : v;
  const from = (t, r) => {
    if (r === null || r === undefined) return (t === "ListNode" || t === "TreeNode") ? [] : null;
    if (t === "ListNode") { const o = []; let n = 0; while (r && n++ < 200000) { o.push(r.val); r = r.next; } return o; }
    if (t === "TreeNode") {
      const o = [], q = [r]; let qi = 0;
      while (qi < q.length && o.length < 400000) { const n = q[qi++]; if (!n) { o.push(null); continue; } o.push(n.val); q.push(n.left || null, n.right || null); }
      while (o.length && o[o.length - 1] === null) o.pop(); return o;
    }
    if (isSeq(t)) { if (typeof r === "string") r = r.split(""); return Array.from(r, x => from(elem(t), x)); }
    if (t === "boolean") return !!r;
    return r;
  };
  for (let i = 0; i < spec.tests.length; i++) {
    try {
      let f = H.fn;
      if (typeof f !== "function" && typeof H.S === "function") { const o = new H.S(); if (typeof o[meta.name] === "function") f = o[meta.name].bind(o); }
      if (typeof f !== "function") throw new Error("no function '" + meta.name + "' found");
      const a = ptypes.map((t, j) => to(t, spec.tests[i][j]));
      const r = f(...a);
      emit(i, oidx === undefined ? from(rtype, r) : from(ptypes[oidx], a[oidx]));
    } catch (e) { emit(i, short(e), true); }
  }
})();
"""


class JavaScript(Lang):
    key, label, ext, tools, leetcode_slug = "javascript", "JavaScript", "js", ("node",), "javascript"

    def jsdoc(self, t):
        if t in ("integer", "long", "double"):
            return "number"
        if t in ("string", "character"):
            return "string"
        if t in ("boolean", "void") or t in NODES:
            return t
        return self.jsdoc(elem(t)) + "[]"

    def starter(self, meta):
        hdr = defs_comment(meta, " * ",
                           ["function ListNode(val, next) {", " *     this.val = (val===undefined ? 0 : val)",
                            " *     this.next = (next===undefined ? null : next)", " * }"],
                           ["function TreeNode(val, left, right) {", " *     this.val = (val===undefined ? 0 : val)",
                            " *     this.left = (left===undefined ? null : left)", " *     this.right = (right===undefined ? null : right)", " * }"])
        lines = ["/**"] + ([hdr, " */", "/**"] if hdr else [])
        lines += [f" * @param {{{self.jsdoc(p['type'])}}} {p['name']}" for p in meta["params"]]
        lines += [f" * @return {{{self.jsdoc(meta['return']['type'])}}}", " */"]
        args = ", ".join(p["name"] for p in meta["params"])
        lines += [f"var {meta['name']} = function({args}) {{", "    ", "};", ""]
        return "\n".join(lines)

    def harness_src(self, meta, code):
        fname = meta["name"]
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", fname):
            raise ValueError("bad function name")
        defs = []
        for node in NODES:
            if not defines(code, rf"(^|\n)\s*(export\s+)?(class|function)\s+{node}\b"):
                defs.append(JS_DEFS[node])
        shim = (f"globalThis.__lg = {{fn: (typeof {fname} !== 'undefined' ? {fname} : undefined), "
                "S: (typeof Solution !== 'undefined' ? Solution : undefined), LN: ListNode, TN: TreeNode};")
        return code + "\n;/* ---- LeetClaude harness ---- */\n" + "\n".join(defs) + "\n;" + shim + "\n"

    def prepare(self, work, meta, tests, code):
        (work / "package.json").write_text('{"type": "commonjs"}')
        (work / "spec.json").write_text(json.dumps({"meta": meta, "tests": tests}))
        (work / f"solution.{self.ext}").write_text(self.harness_src(meta, code))
        (work / "lg_main.js").write_text(JS_MAIN)
        return None, ["node", "lg_main.js", f"solution.{self.ext}", "spec.json"]


# Type check close to LeetCode's TypeScript ("--alwaysStrict --strictBindCallApply --strictFunctionTypes
# --target ES20xx"): no strictNullChecks or noImplicitAny. esnext gives the newest lib tsc knows (+ DOM).
TSC_FLAGS = ["--noEmit", "--pretty", "false", "--skipLibCheck", "--target", "esnext", "--strict", "false",
             "--alwaysStrict", "--strictBindCallApply", "--strictFunctionTypes", "--typeRoots", "types"]
TS_NOTE = "Type errors aren't checked: install TypeScript (npm i -g typescript) to enable it."
# The classes from the starter's comment block, which LeetCode declares for the user.
TS_ENV = """declare class ListNode {
    val: number
    next: ListNode | null
    constructor(val?: number, next?: ListNode | null)
}
declare class TreeNode {
    val: number
    left: TreeNode | null
    right: TreeNode | null
    constructor(val?: number, left?: TreeNode | null, right?: TreeNode | null)
}
"""
# Runtime (Node) has these; older tsc libs don't, so declare them rather than reject valid code.
TS_ES2023 = """interface Array<T> {
    findLast<S extends T>(predicate: (value: T, index: number, array: T[]) => value is S, thisArg?: any): S | undefined;
    findLast(predicate: (value: T, index: number, array: T[]) => unknown, thisArg?: any): T | undefined;
    findLastIndex(predicate: (value: T, index: number, array: T[]) => unknown, thisArg?: any): number;
    toReversed(): T[];
    toSorted(compareFn?: (a: T, b: T) => number): T[];
    toSpliced(start: number, deleteCount?: number, ...items: T[]): T[];
    with(index: number, value: T): T[];
}
interface ReadonlyArray<T> {
    findLast<S extends T>(predicate: (value: T, index: number, array: readonly T[]) => value is S, thisArg?: any): S | undefined;
    findLast(predicate: (value: T, index: number, array: readonly T[]) => unknown, thisArg?: any): T | undefined;
    findLastIndex(predicate: (value: T, index: number, array: readonly T[]) => unknown, thisArg?: any): number;
    toReversed(): T[];
    toSorted(compareFn?: (a: T, b: T) => number): T[];
    toSpliced(start: number, deleteCount?: number, ...items: T[]): T[];
    with(index: number, value: T): T[];
}
"""
TS_ES2024 = """interface ObjectConstructor {
    groupBy<K extends PropertyKey, T>(items: Iterable<T>, keySelector: (item: T, index: number) => K): Partial<Record<K, T[]>>;
}
interface MapConstructor {
    groupBy<K, T>(items: Iterable<T>, keySelector: (item: T, index: number) => K): Map<K, T[]>;
}
"""


@functools.lru_cache(maxsize=4)
def _tsc_version(tsc: str) -> tuple[int, int]:
    """(major, minor) of a tsc on PATH: from its package.json if found, else `tsc --version`; (0, 0) if unknown."""
    real = Path(os.path.realpath(tsc))
    for d in (real.parent.parent, real.parent):
        try:
            pkg = json.loads((d / "package.json").read_text())
        except (OSError, ValueError):
            continue
        m = re.match(r"(\d+)\.(\d+)", str(pkg.get("version", "")))
        if m and "typescript" in str(pkg.get("name", "")):
            return int(m[1]), int(m[2])
    try:
        out = subprocess.run([tsc, "--version"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    m = re.search(r"(\d+)\.(\d+)", out)
    return (int(m[1]), int(m[2])) if m else (0, 0)


class TypeScript(JavaScript):
    key, label, ext, tools, leetcode_slug = "typescript", "TypeScript", "ts", ("node",), "typescript"

    def tstype(self, t):
        if t in ("integer", "long", "double"):
            return "number"
        if t in ("string", "character"):
            return "string"
        if t in ("boolean", "void"):
            return t
        if t in NODES:
            return f"{t} | null"
        inner = self.tstype(elem(t))
        return f"({inner})[]" if "|" in inner else inner + "[]"

    def starter(self, meta):
        hdr = defs_comment(meta, " * ",
                           ["class ListNode {", " *     val: number", " *     next: ListNode | null",
                            " *     constructor(val?: number, next?: ListNode | null) {",
                            " *         this.val = (val===undefined ? 0 : val)",
                            " *         this.next = (next===undefined ? null : next)", " *     }", " * }"],
                           ["class TreeNode {", " *     val: number", " *     left: TreeNode | null", " *     right: TreeNode | null",
                            " *     constructor(val?: number, left?: TreeNode | null, right?: TreeNode | null) {",
                            " *         this.val = (val===undefined ? 0 : val)",
                            " *         this.left = (left===undefined ? null : left)",
                            " *         this.right = (right===undefined ? null : right)", " *     }", " * }"])
        args = ", ".join(f"{p['name']}: {self.tstype(p['type'])}" for p in meta["params"])
        rt = self.tstype(meta["return"]["type"])
        body = "    " + (" // Do not return anything, modify it in-place instead." if rt == "void" else "")
        out = (f"/**\n{hdr}\n */\n\n" if hdr else "")
        return out + f"function {meta['name']}({args}): {rt} {{\n{body}\n}};\n"

    def prepare(self, work, meta, tests, code):
        build, run = super().prepare(work, meta, tests, code)
        return build, ["node", "--experimental-transform-types", "--no-warnings", "lg_main.js", f"solution.{self.ext}", "spec.json"]

    def typecheck(self, work, code):
        # Node only strips types, so run tsc (if installed) on the user's code, unchanged, in its own dir.
        tsc = shutil.which("tsc")
        if not tsc:
            return None, None, TS_NOTE
        ver = _tsc_version(tsc)
        d = work / "tsc"
        (d / "types").mkdir(parents=True)  # empty typeRoots: no stray @types from parent dirs
        (d / "lg_env.d.ts").write_text(TS_ENV + (TS_ES2023 if ver < (5, 0) else "") + (TS_ES2024 if ver < (5, 4) else ""))
        flags = list(TSC_FLAGS)
        if ver >= (4, 7):
            flags += ["--moduleDetection", "force"]  # a module, as Node runs it: user names shadow the globals
        else:
            code += "\nexport {};\n"  # same effect; appended so no user line moves
        (d / "solution.ts").write_text(code)
        return [tsc, *flags, "solution.ts", "lg_env.d.ts"], d, None

    def typecheck_result(self, rc, out):
        if rc == 0:
            return None, None
        keep, mine = [], False
        for line in out.splitlines():
            if not line.strip():
                continue
            if not line.startswith(" "):  # a new diagnostic; indented lines continue it
                mine = line.startswith("solution.ts(")
            if mine:
                keep.append(line.rstrip())
        if keep:
            return "\n".join(keep), None
        first = next((l.strip() for l in out.splitlines() if l.strip()), f"exit {rc}")
        return None, f"Type errors aren't checked: tsc failed ({first[:200]})."


# ---------- Go
GO_LIST = "type ListNode struct {\n\tVal  int\n\tNext *ListNode\n}\n"
GO_TREE = "type TreeNode struct {\n\tVal   int\n\tLeft  *TreeNode\n\tRight *TreeNode\n}\n"
GO_IMPORTS = {
    "sort": r"\bsort\.(Ints|Strings|Float64s|Slice|SliceStable|Sort|Stable|Search|SearchInts|SearchStrings|IntSlice|StringSlice|Reverse|IntsAreSorted)\b",
    "strings": r"\bstrings\.[A-Z]", "strconv": r"\bstrconv\.[A-Z]", "math": r"\bmath\.[A-Z]",
    "math/bits": r"\bbits\.(OnesCount|Len|TrailingZeros|LeadingZeros|Reverse|RotateLeft)\w*\(",
    "container/heap": r"\bheap\.(Init|Push|Pop|Fix|Remove|Interface)\b", "container/list": r"\blist\.New\(",
    "unicode": r"\bunicode\.[A-Z]", "fmt": r"\bfmt\.[A-Z]",
    "slices": r"\bslices\.(Sort|SortFunc|SortStableFunc|Contains|Index|Reverse|Max|Min|BinarySearch|Equal|Insert|Delete|IndexFunc|ContainsFunc)\w*\(",
    "maps": r"\bmaps\.(Keys|Values|Clone|Copy|Equal|DeleteFunc)\(", "bytes": r"\bbytes\.(Equal|Compare|Contains|Index|Split|Join|Buffer|NewBuffer|Repeat)\b",
    "cmp": r"\bcmp\.(Compare|Less|Or)\(", "math/rand": r"\brand\.(Intn|Int|Shuffle|Perm|Float64)\(",
}
# Comments, raw strings, interpreted strings, runes. Matches go left to right, so whichever starts first wins
# (a "//" inside a string is part of the string; a quote inside a comment is part of the comment).
GO_NONCODE = re.compile(r'//[^\n]*|/\*.*?(?:\*/|\Z)|`[^`]*(?:`|\Z)|"(?:\\.|[^"\\\n])*"?|\'(?:\\.|[^\'\\\n])*\'?', re.S)


def go_code_only(code: str) -> str:
    """Go source with comments and string/rune literals blanked (newlines kept), for regex scans."""
    def blank(m):
        s = m.group()
        return {'"': '""', "`": '""', "'": "' '"}.get(s[0], " ") + "\n" * s.count("\n")
    return GO_NONCODE.sub(blank, code)
GO_HARNESS = r'''package main

import (
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	lgrt "runtime"
	"strconv"
	"strings"
)

const lgM, lgME = "@@LG@@", "@@LGE@@"

__DEFS__
func lgQ(s string) string { b, _ := json.Marshal(s); return string(b) }
func lgDec[T any](raw json.RawMessage) T {
	var v T
	if err := json.Unmarshal(raw, &v); err != nil {
		panic("bad test input: " + err.Error())
	}
	return v
}
func lgByte(raw json.RawMessage) byte { return lgDec[string](raw)[0] }
func lgBytes(raw json.RawMessage) []byte {
	ss := lgDec[[]string](raw)
	b := make([]byte, len(ss))
	for i, s := range ss {
		b[i] = s[0]
	}
	return b
}
func lgBytes2(raw json.RawMessage) [][]byte {
	rows := lgDec[[]json.RawMessage](raw)
	out := make([][]byte, len(rows))
	for i, r := range rows {
		out[i] = lgBytes(r)
	}
	return out
}
func lgList(raw json.RawMessage) *ListNode {
	a := lgDec[[]int](raw)
	var h *ListNode
	for i := len(a) - 1; i >= 0; i-- {
		h = &ListNode{Val: a[i], Next: h}
	}
	return h
}
func lgLists(raw json.RawMessage) []*ListNode {
	rows := lgDec[[]json.RawMessage](raw)
	out := make([]*ListNode, len(rows))
	for i, r := range rows {
		out[i] = lgList(r)
	}
	return out
}
func lgTree(raw json.RawMessage) *TreeNode {
	a := lgDec[[]*int](raw)
	if len(a) == 0 || a[0] == nil {
		return nil
	}
	root := &TreeNode{Val: *a[0]}
	q := []*TreeNode{root}
	i := 1
	for len(q) > 0 && i < len(a) {
		n := q[0]
		q = q[1:]
		if i < len(a) && a[i] != nil {
			n.Left = &TreeNode{Val: *a[i]}
			q = append(q, n.Left)
		}
		i++
		if i < len(a) && a[i] != nil {
			n.Right = &TreeNode{Val: *a[i]}
			q = append(q, n.Right)
		}
		i++
	}
	return root
}
func lgSerList(h *ListNode) string {
	parts := []string{}
	for n := 0; h != nil && n < 200000; n++ {
		parts = append(parts, strconv.Itoa(h.Val))
		h = h.Next
	}
	return "[" + strings.Join(parts, ",") + "]"
}
func lgSerTree(r *TreeNode) string {
	if r == nil {
		return "[]"
	}
	out := []string{}
	q := []*TreeNode{r}
	for len(q) > 0 && len(out) < 400000 {
		n := q[0]
		q = q[1:]
		if n == nil {
			out = append(out, "null")
			continue
		}
		out = append(out, strconv.Itoa(n.Val))
		q = append(q, n.Left, n.Right)
	}
	for len(out) > 0 && out[len(out)-1] == "null" {
		out = out[:len(out)-1]
	}
	return "[" + strings.Join(out, ",") + "]"
}
func lgSer(v interface{}) string {
	switch x := v.(type) {
	case nil:
		return "null"
	case *ListNode:
		return lgSerList(x)
	case *TreeNode:
		return lgSerTree(x)
	case byte:
		return lgQ(string([]byte{x}))
	case []byte:
		p := make([]string, len(x))
		for i, c := range x {
			p[i] = lgQ(string([]byte{c}))
		}
		return "[" + strings.Join(p, ",") + "]"
	case [][]byte:
		p := make([]string, len(x))
		for i, row := range x {
			p[i] = lgSer(row)
		}
		return "[" + strings.Join(p, ",") + "]"
	case []*ListNode:
		p := make([]string, len(x))
		for i, n := range x {
			p[i] = lgSerList(n)
		}
		return "[" + strings.Join(p, ",") + "]"
	case []*TreeNode:
		p := make([]string, len(x))
		for i, n := range x {
			p[i] = lgSerTree(n)
		}
		return "[" + strings.Join(p, ",") + "]"
	}
	// Any other slice: element-wise, so nil slices print as [] (as on LeetCode), not null.
	if rv := reflect.ValueOf(v); rv.Kind() == reflect.Slice {
		p := make([]string, rv.Len())
		for i := range p {
			p[i] = lgSer(rv.Index(i).Interface())
		}
		return "[" + strings.Join(p, ",") + "]"
	}
	b, err := json.Marshal(v)
	if err != nil {
		return lgQ(fmt.Sprint(v))
	}
	return string(b)
}
// The panicking stack's frames in the user's file (solution.go, also under its //line name), innermost first.
func lgWhere() string {
	pcs := make([]uintptr, 128)
	frames := lgrt.CallersFrames(pcs[:lgrt.Callers(2, pcs)])
	out := ""
	for k := 0; k < 6; {
		f, more := frames.Next()
		if f.File == "solution.go" || strings.HasSuffix(f.File, "/solution.go") {
			out += fmt.Sprintf("\n  at solution.go:%d (%s)", f.Line, strings.TrimPrefix(f.Function, "main."))
			k++
		}
		if !more {
			break
		}
	}
	return out
}
func lgRun(i int, f func() string) {
	defer func() {
		if e := recover(); e != nil {
			fmt.Printf("\n%s%d\t%s\n", lgME, i, lgQ(fmt.Sprint(e)+lgWhere()))
		}
	}()
	s := f()
	fmt.Printf("\n%s%d\t%s\n", lgM, i, s)
}
func main() {
	data, _ := os.ReadFile(os.Args[1])
	var tests [][]json.RawMessage
	json.Unmarshal(data, &tests)
	for i, t := range tests {
		t := t
		lgRun(i, func() string {
			__CALL__
		})
	}
}
'''


class Go(Lang):
    key, label, ext, tools, leetcode_slug = "go", "Go", "go", ("go",), "golang"

    def gotype(self, t):
        t = norm(t)
        m = {"integer": "int", "long": "int64", "double": "float64", "boolean": "bool", "string": "string",
             "character": "byte", "ListNode": "*ListNode", "TreeNode": "*TreeNode"}
        if t in m:
            return m[t]
        return "[]" + self.gotype(elem(t))

    def supports(self, meta):
        return meta_supported(meta) and not any(norm(t) in ("TreeNode[][]", "ListNode[][]") for t in all_types(meta))

    def starter(self, meta):
        hdr = defs_comment(meta, " * ", ["type ListNode struct {", " *     Val int", " *     Next *ListNode", " * }"],
                           ["type TreeNode struct {", " *     Val int", " *     Left *TreeNode", " *     Right *TreeNode", " * }"])
        args = ", ".join(f"{p['name']} {self.gotype(p['type'])}" for p in meta["params"])
        rt = meta["return"]["type"]
        ret = "" if rt == "void" else " " + self.gotype(rt)
        out = (f"/**\n{hdr}\n */\n" if hdr else "")
        return out + f"func {meta['name']}({args}){ret} {{\n    \n}}\n"

    def decoder(self, t, raw):
        t = norm(t)
        special = {"character": "lgByte", "character[]": "lgBytes", "character[][]": "lgBytes2",
                   "ListNode": "lgList", "ListNode[]": "lgLists", "TreeNode": "lgTree"}
        if t in special:
            return f"{special[t]}({raw})"
        return f"lgDec[{self.gotype(t)}]({raw})"

    def prepare(self, work, meta, tests, code):
        stripped = go_code_only(code)
        defs = ""
        if not re.search(r"type\s+ListNode\s+struct", stripped):
            defs += GO_LIST
        if not re.search(r"type\s+TreeNode\s+struct", stripped):
            defs += GO_TREE
        stmts = [f"a{j} := {self.decoder(p['type'], f't[{j}]')}" for j, p in enumerate(meta["params"])]
        args = ", ".join(f"a{j}" for j in range(len(meta["params"])))
        oidx = (meta.get("output") or {}).get("paramindex")
        if meta["return"]["type"] == "void":
            stmts += [f"{meta['name']}({args})", f"return lgSer(a{oidx})"]
        else:
            stmts += [f"r := {meta['name']}({args})", "return lgSer(r)"]
        # a0 might be unused only when there are no params; Go then needs no guard.
        (work / "main.go").write_text(GO_HARNESS.replace("__DEFS__", defs).replace("__CALL__", "\n\t\t\t".join(stmts)))
        imps = [] if re.search(r"^\s*import\b", stripped, re.M) else [p for p, rx in GO_IMPORTS.items() if re.search(rx, stripped)]
        imp = ("import (" + "; ".join(f'"{p}"' for p in imps) + ")") if imps else ""
        head = []
        if re.search(r"^\s*package\s+\w+", stripped, re.M):
            pkg = re.search(r"^[ \t]*package[ \t]+\w+", code, re.M)
            if imp and pkg:  # imports go on the package line itself, so the user's line numbers don't move
                code = code[:pkg.end()] + "; " + imp + code[pkg.end():]
        else:
            head = ["package main"] + ([imp] if imp else [])
        prefix = ("; ".join(head) + "\n//line solution.go:1\n") if head else ""
        (work / "solution.go").write_text(prefix + code)
        (work / "tests.json").write_text(json.dumps(tests))
        return ["go", "build", "-o", "prog", "main.go", "solution.go"], ["./prog", "tests.json"]


# ---------- Java
JAVA_LIST = ("class ListNode { int val; ListNode next; ListNode() {} ListNode(int val) { this.val = val; } "
             "ListNode(int val, ListNode next) { this.val = val; this.next = next; } }\n")
JAVA_TREE = ("class TreeNode { int val; TreeNode left; TreeNode right; TreeNode() {} TreeNode(int val) { this.val = val; } "
             "TreeNode(int val, TreeNode left, TreeNode right) { this.val = val; this.left = left; this.right = right; } }\n")
JAVA_MAIN = r'''
public class Main {
  static final String M = "@@LG@@", ME = "@@LGE@@";
  static final boolean NN = __NN__;  // output is ListNode/TreeNode-based: null node -> []
  static String Q(String s) {
    StringBuilder b = new StringBuilder("\"");
    for (char c : s.toCharArray()) {
      switch (c) {
        case '"': b.append("\\\""); break;
        case '\\': b.append("\\\\"); break;
        case '\n': b.append("\\n"); break;
        case '\r': b.append("\\r"); break;
        case '\t': b.append("\\t"); break;
        default: if (c < 0x20) b.append(String.format("\\u%04x", (int) c)); else b.append(c);
      }
    }
    return b.append('"').toString();
  }
  static String J(Object o) {
    if (o == null) return NN ? "[]" : "null";
    if (o instanceof String) return Q((String) o);
    if (o instanceof Character) return Q(String.valueOf(o));
    if (o instanceof Boolean || o instanceof Integer || o instanceof Long || o instanceof Short || o instanceof Byte) return o.toString();
    if (o instanceof Double || o instanceof Float) { double d = ((Number) o).doubleValue(); return Double.isFinite(d) ? Double.toString(d) : Q(Double.toString(d)); }
    StringBuilder b = new StringBuilder("[");
    if (o instanceof int[]) { int[] a = (int[]) o; for (int i = 0; i < a.length; i++) { if (i > 0) b.append(','); b.append(a[i]); } }
    else if (o instanceof long[]) { long[] a = (long[]) o; for (int i = 0; i < a.length; i++) { if (i > 0) b.append(','); b.append(a[i]); } }
    else if (o instanceof double[]) { double[] a = (double[]) o; for (int i = 0; i < a.length; i++) { if (i > 0) b.append(','); b.append(J(a[i])); } }
    else if (o instanceof boolean[]) { boolean[] a = (boolean[]) o; for (int i = 0; i < a.length; i++) { if (i > 0) b.append(','); b.append(a[i]); } }
    else if (o instanceof char[]) { char[] a = (char[]) o; for (int i = 0; i < a.length; i++) { if (i > 0) b.append(','); b.append(Q(String.valueOf(a[i]))); } }
    else if (o instanceof Object[]) { Object[] a = (Object[]) o; for (int i = 0; i < a.length; i++) { if (i > 0) b.append(','); b.append(J(a[i])); } }
    else if (o instanceof Collection) { int i = 0; for (Object x : (Collection<?>) o) { if (i++ > 0) b.append(','); b.append(J(x)); } }
    else if (o instanceof ListNode) { ListNode h = (ListNode) o; int n = 0; while (h != null && n < 200000) { if (n++ > 0) b.append(','); b.append(h.val); h = h.next; } }
    else if (o instanceof TreeNode) {
      List<String> out = new ArrayList<>(); ArrayDeque<Object> q = new ArrayDeque<>(); q.add(o);
      while (!q.isEmpty() && out.size() < 400000) { Object x = q.poll(); if (!(x instanceof TreeNode)) { out.add("null"); continue; } TreeNode t = (TreeNode) x; out.add(String.valueOf(t.val)); q.add(t.left == null ? (Object) "n" : t.left); q.add(t.right == null ? (Object) "n" : t.right); }
      while (!out.isEmpty() && out.get(out.size() - 1).equals("null")) out.remove(out.size() - 1);
      b.append(String.join(",", out));
    }
    else return Q(o.toString());
    return b.append(']').toString();
  }
  static ListNode BL(int[] a) { ListNode h = null; for (int i = a.length - 1; i >= 0; i--) h = new ListNode(a[i], h); return h; }
  static TreeNode BT(Integer[] a) {
    if (a.length == 0 || a[0] == null) return null;
    TreeNode root = new TreeNode(a[0]); ArrayDeque<TreeNode> q = new ArrayDeque<>(); q.add(root); int i = 1;
    while (!q.isEmpty() && i < a.length) {
      TreeNode n = q.poll();
      if (i < a.length && a[i] != null) { n.left = new TreeNode(a[i]); q.add(n.left); } i++;
      if (i < a.length && a[i] != null) { n.right = new TreeNode(a[i]); q.add(n.right); } i++;
    }
    return root;
  }
  @SafeVarargs static <T> List<T> L(T... xs) { return new ArrayList<>(Arrays.asList(xs)); }
  static void emit(String marker, int i, String s) { System.out.print("\n" + marker + i + "\t" + s + "\n"); System.out.flush(); }
__TESTS__
  public static void main(String[] args) throws Exception {
    Thread t = new Thread(null, () -> {
      for (int i = 0; i < __N__; i++) {
        try { emit(M, i, run(i)); }
        catch (Throwable e) {
          StringBuilder sb = new StringBuilder(e.toString());
          int k = 0; for (StackTraceElement el : e.getStackTrace()) { if (el.getClassName().equals("Main")) break; if (k++ < 6) sb.append("\n  at ").append(el); }
          emit(ME, i, Q(sb.toString()));
        }
      }
    }, "lg", 1L << 28);
    t.start(); t.join();
  }
}
'''


class Java(Lang):
    key, label, ext, tools, leetcode_slug = "java", "Java", "java", ("javac", "java"), "java"
    PRIM = {"integer": "int", "long": "long", "double": "double", "boolean": "boolean", "string": "String", "character": "char"}
    BOX = {"integer": "Integer", "long": "Long", "double": "Double", "boolean": "Boolean", "string": "String", "character": "Character"}

    def jdecl(self, t, boxed=False):
        if t in self.PRIM:
            return (self.BOX if boxed else self.PRIM)[t]
        if t in NODES or t == "void":
            return t
        if is_list(t):
            return f"List<{self.jdecl(elem(t), True)}>"
        return self.jdecl(elem(t)) + "[]"

    def jinit(self, t, v):
        e = elem(t)
        if e.endswith("[]"):
            return "{" + ",".join(self.jinit(e, x) for x in v) + "}"
        return "{" + ",".join(self.jlit(e, x) for x in v) + "}"

    def jlit(self, t, v):
        if v is None and t not in NODES:
            return "null"
        if t == "integer":
            return str(int(v))
        if t == "long":
            return f"{int(v)}L"
        if t == "double":
            return dlit(v)
        if t == "boolean":
            return "true" if v else "false"
        if t == "string":
            return cstr(v)
        if t == "character":
            return cchar(v)
        if t == "ListNode":
            return "BL(new int[]{" + ",".join(str(x) for x in (v or [])) + "})"
        if t == "TreeNode":
            return "BT(new Integer[]{" + ",".join("null" if x is None else str(x) for x in (v or [])) + "})"
        if is_list(t):
            return "L(" + ",".join(self.jlit(elem(t), x) for x in v) + ")"
        return "new " + self.jdecl(t) + self.jinit(t, v)

    def starter(self, meta):
        hdr = defs_comment(meta, " * ",
                           ["public class ListNode {", " *     int val;", " *     ListNode next;", " *     ListNode() {}",
                            " *     ListNode(int val) { this.val = val; }",
                            " *     ListNode(int val, ListNode next) { this.val = val; this.next = next; }", " * }"],
                           ["public class TreeNode {", " *     int val;", " *     TreeNode left;", " *     TreeNode right;",
                            " *     TreeNode() {}", " *     TreeNode(int val) { this.val = val; }",
                            " *     TreeNode(int val, TreeNode left, TreeNode right) {", " *         this.val = val;",
                            " *         this.left = left;", " *         this.right = right;", " *     }", " * }"])
        args = ", ".join(f"{self.jdecl(p['type'])} {p['name']}" for p in meta["params"])
        out = (f"/**\n{hdr}\n */\n" if hdr else "")
        return out + f"class Solution {{\n    public {self.jdecl(meta['return']['type'])} {meta['name']}({args}) {{\n        \n    }}\n}}\n"

    def prepare(self, work, meta, tests, code):
        user = re.sub(r"\bpublic\s+class\s+Solution\b", "class Solution", code)
        defs = ("" if defines(code, r"\bclass\s+ListNode\b") else JAVA_LIST) + \
               ("" if defines(code, r"\bclass\s+TreeNode\b") else JAVA_TREE)
        ptypes = [p["type"] for p in meta["params"]]
        oidx = (meta.get("output") or {}).get("paramindex")
        fns, cases = [], []
        for i, args in enumerate(tests):
            body = [f"{self.jdecl(t)} a{j} = {self.jlit(t, v)};" for j, (t, v) in enumerate(zip(ptypes, args))]
            call = f"new Solution().{meta['name']}({', '.join(f'a{j}' for j in range(len(ptypes)))})"
            if meta["return"]["type"] == "void":
                body += [f"{call};", f"return J(a{oidx});"]
            else:
                body += [f"Object r = {call};", "return J(r);"]
            fns.append(f"  static String t{i}() throws Exception {{ {' '.join(body)} }}")
            cases.append(f"case {i}: return t{i}();")
        tests_src = "\n".join(fns) + "\n  static String run(int i) throws Exception { switch (i) { " + " ".join(cases) + " } return \"null\"; }"
        out_t = ptypes[oidx] if meta["return"]["type"] == "void" else meta["return"]["type"]
        src = ("import java.util.*; import java.util.stream.*; import java.util.function.*; " + user + "\n" + defs +
               JAVA_MAIN.replace("__TESTS__", tests_src).replace("__N__", str(len(tests)))
               .replace("__NN__", "true" if base(out_t) in NODES else "false"))
        (work / "Main.java").write_text(src)
        return ["javac", "-nowarn", "-encoding", "UTF-8", "-d", ".", "Main.java"], ["java", "-cp", ".", "Main"]


# ---------- C++
CPP_PRELUDE = """#include <algorithm>
#include <array>
#include <bitset>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <functional>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <list>
#include <map>
#include <memory>
#include <numeric>
#include <optional>
#include <queue>
#include <set>
#include <sstream>
#include <stack>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
using namespace std;
"""
CPP_LIST = ("struct ListNode { int val; ListNode *next; ListNode() : val(0), next(nullptr) {} ListNode(int x) : val(x), next(nullptr) {} "
            "ListNode(int x, ListNode *next) : val(x), next(next) {} };\n")
CPP_TREE = ("struct TreeNode { int val; TreeNode *left; TreeNode *right; TreeNode() : val(0), left(nullptr), right(nullptr) {} "
            "TreeNode(int x) : val(x), left(nullptr), right(nullptr) {} "
            "TreeNode(int x, TreeNode *left, TreeNode *right) : val(x), left(left), right(right) {} };\n")
CPP_HARNESS = r'''
#line 1 "lg_harness.cpp"
static const int LGN = INT_MIN;
static string lgQ(const string& s) {
  string o = "\"";
  for (unsigned char c : s) {
    if (c == '"') o += "\\\""; else if (c == '\\') o += "\\\\"; else if (c == '\n') o += "\\n";
    else if (c == '\r') o += "\\r"; else if (c == '\t') o += "\\t";
    else if (c < 0x20) { char buf[8]; snprintf(buf, sizeof buf, "\\u%04x", c); o += buf; }
    else o += (char)c;
  }
  return o + "\"";
}
static string J(int x) { return to_string(x); }
static string J(long x) { return to_string(x); }
static string J(long long x) { return to_string(x); }
static string J(unsigned x) { return to_string(x); }
static string J(unsigned long x) { return to_string(x); }
static string J(unsigned long long x) { return to_string(x); }
static string J(double x) { if (!isfinite(x)) return lgQ(to_string(x)); ostringstream o; o << setprecision(15) << x; string s = o.str(); return s; }
static string J(float x) { return J((double)x); }
static string J(bool x) { return x ? "true" : "false"; }
static string J(char c) { return lgQ(string(1, c)); }
static string J(const string& s) { return lgQ(s); }
static string J(const char* s) { return lgQ(s); }
static string J(ListNode* h) { string o = "["; int n = 0; while (h && n < 200000) { if (n++) o += ","; o += to_string(h->val); h = h->next; } return o + "]"; }
static string J(TreeNode* r) {
  if (!r) return "[]";
  vector<string> out; deque<TreeNode*> q{r};
  while (!q.empty() && out.size() < 400000) { TreeNode* n = q.front(); q.pop_front(); if (!n) { out.push_back("null"); continue; } out.push_back(to_string(n->val)); q.push_back(n->left); q.push_back(n->right); }
  while (!out.empty() && out.back() == "null") out.pop_back();
  string o = "["; for (size_t i = 0; i < out.size(); i++) { if (i) o += ","; o += out[i]; } return o + "]";
}
template <class T> string J(const vector<T>& v) { string o = "["; for (size_t i = 0; i < v.size(); i++) { if (i) o += ","; o += J(static_cast<T>(v[i])); } return o + "]"; }
static ListNode* lgBL(vector<int> a) { ListNode* h = nullptr; for (int i = (int)a.size() - 1; i >= 0; i--) h = new ListNode(a[i], h); return h; }
static TreeNode* lgBT(vector<int> a) {
  if (a.empty() || a[0] == LGN) return nullptr;
  TreeNode* root = new TreeNode(a[0]); deque<TreeNode*> q{root}; size_t i = 1;
  while (!q.empty() && i < a.size()) {
    TreeNode* n = q.front(); q.pop_front();
    if (i < a.size() && a[i] != LGN) { n->left = new TreeNode(a[i]); q.push_back(n->left); } i++;
    if (i < a.size() && a[i] != LGN) { n->right = new TreeNode(a[i]); q.push_back(n->right); } i++;
  }
  return root;
}
static void lgEmit(const char* m, int i, const string& s) { cout << "\n" << m << i << "\t" << s << "\n" << flush; }
int main() {
__TESTS__
  return 0;
}
'''


class Cpp(Lang):
    key, label, ext, tools, leetcode_slug = "cpp", "C++", "cpp", ("c++",), "cpp"
    M = {"integer": "int", "long": "long long", "double": "double", "boolean": "bool", "string": "string",
         "character": "char", "ListNode": "ListNode*", "TreeNode": "TreeNode*", "void": "void"}

    def cdecl(self, t):
        t = norm(t)
        return self.M[t] if t in self.M else f"vector<{self.cdecl(elem(t))}>"

    def clit(self, t, v):
        t = norm(t)
        if t == "integer":
            return str(int(v)) if int(v) != -2**31 else "INT_MIN"
        if t == "long":
            return f"{int(v)}LL" if int(v) != -2**63 else "LLONG_MIN"
        if t == "double":
            return dlit(v)
        if t == "boolean":
            return "true" if v else "false"
        if t == "string":
            return f"string({cstr(v)})"
        if t == "character":
            return cchar(v)
        if t == "ListNode":
            return "lgBL({" + ",".join(str(x) for x in (v or [])) + "})"
        if t == "TreeNode":
            return "lgBT({" + ",".join("LGN" if x is None else str(x) for x in (v or [])) + "})"
        return self.cdecl(t) + "{" + ",".join(self.clit(elem(t), x) for x in v) + "}"

    def starter(self, meta):
        hdr = defs_comment(meta, " * ",
                           ["struct ListNode {", " *     int val;", " *     ListNode *next;", " *     ListNode() : val(0), next(nullptr) {}",
                            " *     ListNode(int x) : val(x), next(nullptr) {}", " *     ListNode(int x, ListNode *next) : val(x), next(next) {}", " * };"],
                           ["struct TreeNode {", " *     int val;", " *     TreeNode *left;", " *     TreeNode *right;",
                            " *     TreeNode() : val(0), left(nullptr), right(nullptr) {}",
                            " *     TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}",
                            " *     TreeNode(int x, TreeNode *left, TreeNode *right) : val(x), left(left), right(right) {}", " * };"])

        def ptype(t):
            d = self.cdecl(t)
            return d + "&" if is_seq(t) else d
        args = ", ".join(f"{ptype(p['type'])} {p['name']}" for p in meta["params"])
        out = (f"/**\n{hdr}\n */\n" if hdr else "")
        return out + f"class Solution {{\npublic:\n    {self.cdecl(meta['return']['type'])} {meta['name']}({args}) {{\n        \n    }}\n}};\n"

    def prepare(self, work, meta, tests, code):
        defs = ("" if defines(code, r"\b(struct|class)\s+ListNode\s*\{") else CPP_LIST) + \
               ("" if defines(code, r"\b(struct|class)\s+TreeNode\s*\{") else CPP_TREE)
        ptypes = [p["type"] for p in meta["params"]]
        oidx = (meta.get("output") or {}).get("paramindex")
        blocks = []
        for i, args in enumerate(tests):
            decl = " ".join(f"{self.cdecl(t)} a{j} = {self.clit(t, v)};" for j, (t, v) in enumerate(zip(ptypes, args)))
            call = f"lgS.{meta['name']}({', '.join(f'a{j}' for j in range(len(ptypes)))})"
            if meta["return"]["type"] == "void":
                tail = f"{call}; lgEmit(\"@@LG@@\", {i}, J(a{oidx}));"
            else:
                tail = f"auto lgR = {call}; lgEmit(\"@@LG@@\", {i}, J(lgR));"
            blocks.append(f"  try {{ {decl} Solution lgS; {tail} }} "
                          f"catch (const exception& e) {{ lgEmit(\"@@LGE@@\", {i}, lgQ(string(\"exception: \") + e.what())); }} "
                          f"catch (...) {{ lgEmit(\"@@LGE@@\", {i}, lgQ(\"unknown exception\")); }}")
        src = CPP_PRELUDE + defs + '#line 1 "solution.cpp"\n' + code + "\n" + CPP_HARNESS.replace("__TESTS__", "\n".join(blocks))
        (work / "main.cpp").write_text(src)
        flags = ["c++", "-std=c++17", "-O1", "-w", "-o", "prog", "main.cpp"]
        if sys.platform == "darwin":
            flags += ["-Wl,-stack_size,0x10000000"]
        return flags, ["./prog"]


# ---------- Rust
RUST_LIST = """#[derive(PartialEq, Eq, Clone, Debug)]
pub struct ListNode { pub val: i32, pub next: Option<Box<ListNode>> }
impl ListNode { #[inline] fn new(val: i32) -> Self { ListNode { next: None, val } } }
"""
RUST_TREE = """#[derive(Debug, PartialEq, Eq)]
pub struct TreeNode { pub val: i32, pub left: Option<Rc<RefCell<TreeNode>>>, pub right: Option<Rc<RefCell<TreeNode>>> }
impl TreeNode { #[inline] pub fn new(val: i32) -> Self { TreeNode { val, left: None, right: None } } }
"""
RUST_HARNESS = r'''
// ---- LeetClaude harness ----
// Like LeetCode: Rc/RefCell are pre-imported (globs, so the user's own `use` lines don't clash);
// std::collections etc. are not, so the user writes `use std::collections::HashMap;` themselves.
#[allow(unused_imports)] use std::rc::*;
#[allow(unused_imports)] use std::cell::*;
__DEFS__
fn lgq(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() {
        match c { '"' => o.push_str("\\\""), '\\' => o.push_str("\\\\"), '\n' => o.push_str("\\n"), '\r' => o.push_str("\\r"), '\t' => o.push_str("\\t"),
            c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)), c => o.push(c) }
    }
    o.push('"'); o
}
trait LgJ { fn lgj(&self) -> String; }
impl LgJ for i32 { fn lgj(&self) -> String { self.to_string() } }
impl LgJ for i64 { fn lgj(&self) -> String { self.to_string() } }
impl LgJ for usize { fn lgj(&self) -> String { self.to_string() } }
impl LgJ for f64 { fn lgj(&self) -> String { if self.is_finite() { format!("{:?}", self) } else { lgq(&self.to_string()) } } }
impl LgJ for bool { fn lgj(&self) -> String { self.to_string() } }
impl LgJ for char { fn lgj(&self) -> String { lgq(&self.to_string()) } }
impl LgJ for String { fn lgj(&self) -> String { lgq(self) } }
impl LgJ for &str { fn lgj(&self) -> String { lgq(self) } }
impl LgJ for () { fn lgj(&self) -> String { "null".to_string() } }
impl<T: LgJ> LgJ for Vec<T> { fn lgj(&self) -> String { format!("[{}]", self.iter().map(|x| x.lgj()).collect::<Vec<_>>().join(",")) } }
impl LgJ for Option<Box<ListNode>> {
    fn lgj(&self) -> String {
        let mut o = vec![]; let mut cur = self.as_ref(); let mut n = 0;
        while let Some(node) = cur { if n >= 200000 { break; } o.push(node.val.to_string()); cur = node.next.as_ref(); n += 1; }
        format!("[{}]", o.join(","))
    }
}
impl LgJ for Option<Rc<RefCell<TreeNode>>> {
    fn lgj(&self) -> String {
        let mut o: Vec<String> = vec![]; let mut q: std::collections::VecDeque<Option<Rc<RefCell<TreeNode>>>> = std::collections::VecDeque::new();
        if self.is_none() { return "[]".to_string(); }
        q.push_back(self.clone());
        while let Some(x) = q.pop_front() {
            if o.len() >= 400000 { break; }
            match x { None => o.push("null".to_string()), Some(n) => { let b = n.borrow(); o.push(b.val.to_string()); q.push_back(b.left.clone()); q.push_back(b.right.clone()); } }
        }
        while o.last().map(|s| s == "null").unwrap_or(false) { o.pop(); }
        format!("[{}]", o.join(","))
    }
}
#[allow(dead_code)]
fn lgbl(a: Vec<i32>) -> Option<Box<ListNode>> { let mut h: Option<Box<ListNode>> = None; for v in a.into_iter().rev() { let mut n = ListNode::new(v); n.next = h; h = Some(Box::new(n)); } h }
#[allow(dead_code)]
fn lgbt(a: Vec<Option<i32>>) -> Option<Rc<RefCell<TreeNode>>> {
    if a.is_empty() || a[0].is_none() { return None; }
    let root = Rc::new(RefCell::new(TreeNode::new(a[0].unwrap()))); let mut q = std::collections::VecDeque::new(); q.push_back(root.clone()); let mut i = 1;
    while !q.is_empty() && i < a.len() {
        let n = q.pop_front().unwrap();
        if i < a.len() { if let Some(v) = a[i] { let c = Rc::new(RefCell::new(TreeNode::new(v))); n.borrow_mut().left = Some(c.clone()); q.push_back(c); } } i += 1;
        if i < a.len() { if let Some(v) = a[i] { let c = Rc::new(RefCell::new(TreeNode::new(v))); n.borrow_mut().right = Some(c.clone()); q.push_back(c); } } i += 1;
    }
    Some(root)
}
fn lgrun<F: FnOnce() -> String>(i: usize, f: F) {
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)) {
        Ok(s) => print!("\n@@LG@@{}\t{}\n", i, s),
        Err(e) => {
            let m = if let Some(s) = e.downcast_ref::<&str>() { s.to_string() } else if let Some(s) = e.downcast_ref::<String>() { s.clone() } else { "panic".to_string() };
            print!("\n@@LGE@@{}\t{}\n", i, lgq(&format!("panicked: {}", m)));
        }
    }
}
fn main() {
    let h = std::thread::Builder::new().stack_size(256 << 20).spawn(|| {
__TESTS__
    }).unwrap();
    let _ = h.join();
}
'''


class Rust(Lang):
    key, label, ext, tools, leetcode_slug = "rust", "Rust", "rs", ("rustc",), "rust"
    M = {"integer": "i32", "long": "i64", "double": "f64", "boolean": "bool", "string": "String", "character": "char",
         "ListNode": "Option<Box<ListNode>>", "TreeNode": "Option<Rc<RefCell<TreeNode>>>"}

    def rdecl(self, t):
        t = norm(t)
        return self.M[t] if t in self.M else f"Vec<{self.rdecl(elem(t))}>"

    def rlit(self, t, v):
        t = norm(t)
        if t in ("integer", "long"):
            return str(int(v))
        if t == "double":
            return dlit(v)
        if t == "boolean":
            return "true" if v else "false"
        if t == "string":
            return cstr(v, ctrl=lambda c: "\\x%02x" % ord(c)) + ".to_string()"
        if t == "character":
            return cchar(v)
        if t == "ListNode":
            return "lgbl(vec![" + ",".join(str(x) for x in (v or [])) + "])"
        if t == "TreeNode":
            return "lgbt(vec![" + ",".join("None" if x is None else f"Some({x})" for x in (v or [])) + "])"
        return "vec![" + ",".join(self.rlit(elem(t), x) for x in v) + "]"

    def starter(self, meta):
        hdr = defs_comment(meta, "// ",
                           ["#[derive(PartialEq, Eq, Clone, Debug)]", "// pub struct ListNode {", "//   pub val: i32,",
                            "//   pub next: Option<Box<ListNode>>", "// }", "// ", "// impl ListNode {", "//   #[inline]",
                            "//   fn new(val: i32) -> Self {", "//     ListNode {", "//       next: None,", "//       val",
                            "//     }", "//   }", "// }"],
                           ["#[derive(Debug, PartialEq, Eq)]", "// pub struct TreeNode {", "//   pub val: i32,",
                            "//   pub left: Option<Rc<RefCell<TreeNode>>>,", "//   pub right: Option<Rc<RefCell<TreeNode>>>,", "// }",
                            "// ", "// impl TreeNode {", "//   #[inline]", "//   pub fn new(val: i32) -> Self {", "//     TreeNode {",
                            "//       val,", "//       left: None,", "//       right: None", "//     }", "//   }", "// }"])
        oidx = (meta.get("output") or {}).get("paramindex")
        args = []
        for j, p in enumerate(meta["params"]):
            ty = self.rdecl(p["type"])
            if meta["return"]["type"] == "void" and j == oidx:
                ty = "&mut " + ty
            args.append(f"{snake(p['name'])}: {ty}")
        rt = meta["return"]["type"]
        ret = "" if rt == "void" else f" -> {self.rdecl(rt)}"
        uses_tree = "use std::rc::Rc;\nuse std::cell::RefCell;\n" if uses(meta, "TreeNode") else ""
        return (hdr + "\n" if hdr else "") + uses_tree + \
            f"impl Solution {{\n    pub fn {snake(meta['name'])}({', '.join(args)}){ret} {{\n        \n    }}\n}}\n"

    def prepare(self, work, meta, tests, code):
        defs = ""
        if not defines(code, r"\bstruct\s+Solution\b"):
            defs += "pub struct Solution;\n"
        if not defines(code, r"\bstruct\s+ListNode\b"):
            defs += RUST_LIST
        if not defines(code, r"\bstruct\s+TreeNode\b"):
            defs += RUST_TREE
        ptypes = [p["type"] for p in meta["params"]]
        oidx = (meta.get("output") or {}).get("paramindex")
        name = snake(meta["name"])
        blocks = []
        for i, args in enumerate(tests):
            decl = " ".join(f"let mut a{j}: {self.rdecl(t)} = {self.rlit(t, v)};" for j, (t, v) in enumerate(zip(ptypes, args)))
            if meta["return"]["type"] == "void":
                call_args = ", ".join(f"&mut a{j}" if j == oidx else f"a{j}" for j in range(len(ptypes)))
                tail = f"Solution::{name}({call_args}); a{oidx}.lgj()"
            else:
                call_args = ", ".join(f"a{j}" for j in range(len(ptypes)))
                tail = f"let r = Solution::{name}({call_args}); r.lgj()"
            blocks.append(f"        lgrun({i}, || {{ {decl} {tail} }});")
        (work / "main.rs").write_text(code + "\n" + RUST_HARNESS.replace("__DEFS__", defs).replace("__TESTS__", "\n".join(blocks)))
        return ["rustc", "--edition", "2021", "-A", "warnings", "-C", "opt-level=1", "-o", "prog", "main.rs"], ["./prog"]


# ---------- C#
CS_LIST = "public class ListNode { public int val; public ListNode next; public ListNode(int val = 0, ListNode next = null) { this.val = val; this.next = next; } }\n"
CS_TREE = ("public class TreeNode { public int val; public TreeNode left; public TreeNode right; "
           "public TreeNode(int val = 0, TreeNode left = null, TreeNode right = null) { this.val = val; this.left = left; this.right = right; } }\n")
CS_HARNESS = r'''
#line default
__DEFS__
public static class LgMain {
  static readonly bool NN = __NN__;  // output is ListNode/TreeNode-based: null node -> []
  static string Q(string s) {
    var b = new System.Text.StringBuilder("\"");
    foreach (char c in s) {
      if (c == '"') b.Append("\\\""); else if (c == '\\') b.Append("\\\\"); else if (c == '\n') b.Append("\\n");
      else if (c == '\r') b.Append("\\r"); else if (c == '\t') b.Append("\\t");
      else if (c < 0x20) b.Append("\\u" + ((int)c).ToString("x4")); else b.Append(c);
    }
    return b.Append('"').ToString();
  }
  static string J(object o) {
    var ci = System.Globalization.CultureInfo.InvariantCulture;
    switch (o) {
      case null: return NN ? "[]" : "null";
      case string s: return Q(s);
      case char c: return Q(c.ToString());
      case bool b: return b ? "true" : "false";
      case int or long or short or byte or uint or ulong: return System.Convert.ToString(o, ci);
      case double d: return double.IsFinite(d) ? d.ToString("R", ci) : Q(d.ToString(ci));
      case float f: return ((double)f).ToString("R", ci);
      case ListNode h: { var p = new List<string>(); int n = 0; while (h != null && n++ < 200000) { p.Add(h.val.ToString(ci)); h = h.next; } return "[" + string.Join(",", p) + "]"; }
      case TreeNode r: {
        var o2 = new List<string>(); var q = new Queue<TreeNode>(); q.Enqueue(r);
        while (q.Count > 0 && o2.Count < 400000) { var n = q.Dequeue(); if (n == null) { o2.Add("null"); continue; } o2.Add(n.val.ToString(ci)); q.Enqueue(n.left); q.Enqueue(n.right); }
        while (o2.Count > 0 && o2[o2.Count - 1] == "null") o2.RemoveAt(o2.Count - 1);
        return "[" + string.Join(",", o2) + "]";
      }
      case System.Collections.IEnumerable e: { var p = new List<string>(); foreach (var x in e) p.Add(J(x)); return "[" + string.Join(",", p) + "]"; }
    }
    return Q(o.ToString());
  }
  static ListNode BL(int[] a) { ListNode h = null; for (int i = a.Length - 1; i >= 0; i--) h = new ListNode(a[i], h); return h; }
  static TreeNode BT(int?[] a) {
    if (a.Length == 0 || a[0] == null) return null;
    var root = new TreeNode(a[0].Value); var q = new Queue<TreeNode>(); q.Enqueue(root); int i = 1;
    while (q.Count > 0 && i < a.Length) {
      var n = q.Dequeue();
      if (i < a.Length && a[i] != null) { n.left = new TreeNode(a[i].Value); q.Enqueue(n.left); } i++;
      if (i < a.Length && a[i] != null) { n.right = new TreeNode(a[i].Value); q.Enqueue(n.right); } i++;
    }
    return root;
  }
  static void Emit(string m, int i, string s) { System.Console.Write("\n" + m + i + "\t" + s + "\n"); System.Console.Out.Flush(); }
__TESTS__
  public static void Main(string[] args) {
    var t = new System.Threading.Thread(() => {
      for (int i = 0; i < __N__; i++) {
        try { Emit("@@LG@@", i, Run(i)); }
        catch (System.Exception e) {
          var lines = (e.StackTrace ?? "").Split('\n').Where(l => l.Contains("Solution.cs")).Take(6);
          Emit("@@LGE@@", i, Q(e.GetType().Name + ": " + e.Message + "\n" + string.Join("\n", lines)));
        }
      }
    }, 256 * 1024 * 1024);
    t.Start(); t.Join();
  }
}
'''


class CSharp(Lang):
    key, label, ext, tools, leetcode_slug = "csharp", "C#", "cs", ("dotnet",), "csharp"
    PRIM = {"integer": "int", "long": "long", "double": "double", "boolean": "bool", "string": "string", "character": "char"}

    def csdecl(self, t):
        if t in self.PRIM:
            return self.PRIM[t]
        if t in NODES or t == "void":
            return t
        if is_list(t):
            return f"IList<{self.csdecl(elem(t))}>"
        return self.csdecl(elem(t)) + "[]"

    def cslit(self, t, v):
        if v is None and t not in NODES:
            return "null"
        if t == "integer":
            return str(int(v))
        if t == "long":
            return f"{int(v)}L"
        if t == "double":
            return dlit(v)
        if t == "boolean":
            return "true" if v else "false"
        if t == "string":
            return cstr(v, ctrl=lambda c: "\\u%04x" % ord(c))
        if t == "character":
            return cchar(v)
        if t == "ListNode":
            return "BL(new int[] {" + ",".join(str(x) for x in (v or [])) + "})"
        if t == "TreeNode":
            return "BT(new int?[] {" + ",".join("null" if x is None else str(x) for x in (v or [])) + "})"
        inner = ",".join(self.cslit(elem(t), x) for x in v)
        if is_list(t):
            return f"new List<{self.csdecl(elem(t))}> {{{inner}}}"
        return f"new {self.csdecl(t)} {{{inner}}}"

    def starter(self, meta):
        hdr = defs_comment(meta, " * ",
                           ["public class ListNode {", " *     public int val;", " *     public ListNode next;",
                            " *     public ListNode(int val=0, ListNode next=null) {", " *         this.val = val;",
                            " *         this.next = next;", " *     }", " * }"],
                           ["public class TreeNode {", " *     public int val;", " *     public TreeNode left;", " *     public TreeNode right;",
                            " *     public TreeNode(int val=0, TreeNode left=null, TreeNode right=null) {",
                            " *         this.val = val;", " *         this.left = left;", " *         this.right = right;", " *     }", " * }"])
        args = ", ".join(f"{self.csdecl(p['type'])} {p['name']}" for p in meta["params"])
        out = (f"/**\n{hdr}\n */\n" if hdr else "")
        return out + f"public class Solution {{\n    public {self.csdecl(meta['return']['type'])} {pascal(meta['name'])}({args}) {{\n        \n    }}\n}}\n"

    def prepare(self, work, meta, tests, code):
        # Shared, cached project so incremental builds stay fast (~2s). Guarded by a lock in run().
        proj = RUN_DIR / "csharp"
        proj.mkdir(parents=True, exist_ok=True)
        csproj = proj / "lg.csproj"
        if not csproj.exists():
            major = "9"
            try:
                major = subprocess.run(["dotnet", "--version"], capture_output=True, text=True, timeout=20).stdout.split(".")[0] or "9"
            except (OSError, subprocess.TimeoutExpired):
                pass
            csproj.write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
                f'<TargetFramework>net{major}.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings>'
                '<Nullable>disable</Nullable><InvariantGlobalization>true</InvariantGlobalization>'
                '<NoWarn>$(NoWarn);CS8632;CS0168;CS0219;CS1998;CS0162;CS8600;CS8602;CS8603;CS8604;CS8618;CS8625</NoWarn>'
                '<SatelliteResourceLanguages>en</SatelliteResourceLanguages></PropertyGroup></Project>\n')
        lines = code.split("\n")
        usings = []
        for k, ln in enumerate(lines):
            if re.match(r"^\s*using\s+[\w.]+\s*;\s*$", ln):
                usings.append(ln.strip())
                lines[k] = ""
        user = "\n".join(lines)
        defs = ("" if defines(code, r"\bclass\s+ListNode\b") else CS_LIST) + \
               ("" if defines(code, r"\bclass\s+TreeNode\b") else CS_TREE)
        ptypes = [p["type"] for p in meta["params"]]
        oidx = (meta.get("output") or {}).get("paramindex")
        fns, cases = [], []
        for i, args in enumerate(tests):
            body = [f"{self.csdecl(t)} a{j} = {self.cslit(t, v)};" for j, (t, v) in enumerate(zip(ptypes, args))]
            call = f"new Solution().{pascal(meta['name'])}({', '.join(f'a{j}' for j in range(len(ptypes)))})"
            if meta["return"]["type"] == "void":
                body += [f"{call};", f"return J(a{oidx});"]
            else:
                body += [f"object r = {call};", "return J(r);"]
            fns.append(f"  static string T{i}() {{ {' '.join(body)} }}")
            cases.append(f"case {i}: return T{i}();")
        tests_src = "\n".join(fns) + "\n  static string Run(int i) { switch (i) { " + " ".join(cases) + " } return \"null\"; }"
        out_t = ptypes[oidx] if meta["return"]["type"] == "void" else meta["return"]["type"]
        src = ("\n".join(dict.fromkeys(usings)) + "\n#line 1 \"Solution.cs\"\n" + user + "\n" +
               CS_HARNESS.replace("__DEFS__", defs).replace("__TESTS__", tests_src).replace("__N__", str(len(tests)))
               .replace("__NN__", "true" if base(out_t) in NODES else "false"))
        (proj / "Program.cs").write_text(src)
        build = ["dotnet", "build", str(csproj), "-c", "Release", "-o", str(proj / "out"), "--nologo", "-v", "q", "-clp:NoSummary"]
        return build, ["dotnet", str(proj / "out" / "lg.dll")]


LANGS: dict[str, Lang] = {L.key: L for L in (Python(), JavaScript(), TypeScript(), Ruby(), Go(), Java(), Cpp(), Rust(), CSharp())}
ALIASES = {"py": "python", "python3": "python", "js": "javascript", "node": "javascript", "ts": "typescript",
           "rb": "ruby", "golang": "go", "c++": "cpp", "cc": "cpp", "rs": "rust", "cs": "csharp", "c#": "csharp", "dotnet": "csharp"}


def lang_key(name: str | None) -> str | None:
    if not name:
        return None
    k = name.lower().strip()
    k = ALIASES.get(k, k)
    return k if k in LANGS else None


def available_langs() -> list[str]:
    return [k for k, L in LANGS.items() if L.available()]


# ---------------------------------------------------------------- execution
def _sh(cmd, cwd, timeout, env=None):
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        t0 = time.time()
        p = subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                             start_new_session=True, env=env)
        timed_out = False
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait()
        dt = time.time() - t0
        out.seek(0)
        err.seek(0)
        return (p.returncode, out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace"), dt, timed_out)


def parse_markers(text: str):
    results, user = {}, []
    for line in text.split("\n"):
        k = line.find("@@LG")
        if k >= 0 and (line.startswith(MARKE, k) or line.startswith(MARK, k)):
            if k > 0:
                user.append(line[:k])
            elif user and user[-1] == "":
                user.pop()  # the harness's own "\n" before the marker, not a blank line the user printed
            err = line.startswith(MARKE, k)
            rest = line[k + len(MARKE if err else MARK):]
            idx, _, payload = rest.partition("\t")
            try:
                i = int(idx)
                val = json.loads(payload)
            except ValueError:
                user.append(line)
                continue
            results[i] = ("err", val) if err else ("ok", val)
        else:
            user.append(line)
    return results, "\n".join(user).strip("\n")


def _strip_paths(s: str, *dirs: Path) -> str:
    """Drop scratch-dir prefixes (as given and realpath'd) so messages show bare file names."""
    for d in dirs:
        for v in {str(d), os.path.realpath(d)}:
            s = s.replace(v + "/", "")
    return s


def _clip(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else s[:n] + f"\n… ({len(s) - n} more chars)"


def _typecheck(L: Lang, cmd, cwd, env, out: dict) -> None:
    """Thread body: run L's static check and put its "error" and "note" into out."""
    try:
        rc, so, se, _, to = _sh(cmd, cwd, 60, env)
        if to:
            out["note"] = "Type errors aren't checked: the type check timed out."
        else:
            out["error"], out["note"] = L.typecheck_result(rc, so + "\n" + se)
    except Exception as e:  # never let the checker break a run
        out["note"] = f"Type errors aren't checked: {e}"


def _execute(L: Lang, work: Path, build, cmd, tests: list, timeout: float, env: dict) -> dict:
    if build:
        rc, out, err, dt, to = _sh(build, work, 120, env)
        if to or rc != 0:
            msg = (err + "\n" + out).strip() if not to else "compile timed out"
            msg = _strip_paths(msg, work, RUN_DIR / "csharp")
            msg = "\n".join(l for l in msg.split("\n") if not l.strip().startswith("Determining projects"))
            return {"status": "compile_error", "compile_error": _clip(msg)}
    rc, out, err, dt, to = _sh(cmd, work, timeout, env)
    results, user_out = parse_markers(out)
    results = {i: (k, _strip_paths(v, work, RUN_DIR / "csharp") if k == "err" and isinstance(v, str) else v)
               for i, (k, v) in results.items()}
    err = _strip_paths(err, work)
    if -1 in results:
        return {"status": "compile_error", "compile_error": _clip(str(results[-1][1]))}
    status = "timeout" if to else ("ok" if len(results) >= len(tests) else "crash")
    if status == "crash" and rc is not None and rc < 0:  # e.g. a C++ segfault prints nothing itself
        try:
            sig = signal.Signals(-rc).name
        except ValueError:
            sig = f"signal {-rc}"
        first = min(set(range(len(tests))) - set(results))
        err = (err.rstrip() + "\n" if err.strip() else "") + f"process killed by {sig} while running test {first}"
    return {"status": status, "results": results, "stdout": _clip(user_out), "stderr": _clip(err.strip()),
            "ms": int(dt * 1000), "exit": rc}


def run(lang: str, meta: dict, tests: list, code: str, timeout: float = 10.0) -> dict:
    """Execute code on tests. Returns {status, results:{i:(kind,val)}, stdout, stderr, compile_error, ms},
    plus "note" when something (e.g. TypeScript type checking) was skipped."""
    ensure_home()
    L = LANGS[lang]
    if not L.available():
        return {"status": "unavailable", "compile_error": f"{L.label} toolchain not found on PATH ({', '.join(L.tools)})"}
    work = Path(tempfile.mkdtemp(prefix=f"lg-{lang}-", dir=RUN_DIR))
    lock = th = None
    try:
        if lang == "csharp":
            lock = open(RUN_DIR / ".csharp.lock", "a+")
            fcntl.flock(lock, fcntl.LOCK_EX)
        env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1", NODE_NO_WARNINGS="1")
        env.pop("GOFLAGS", None)
        build, cmd = L.prepare(work, meta, tests, code)
        # The static check (TypeScript's tsc) runs in parallel with build + tests; its errors win.
        tc_cmd, tc_cwd, note = L.typecheck(work, code)
        tc: dict = {}
        if tc_cmd:
            th = threading.Thread(target=_typecheck, args=(L, tc_cmd, tc_cwd, env, tc), daemon=True)
            th.start()
        res = _execute(L, work, build, cmd, tests, timeout, env)
        if th:
            th.join()
            if tc.get("error"):
                res = {"status": "compile_error", "compile_error": _clip(_strip_paths(tc["error"], tc_cwd, work))}
        note = tc.get("note") or note
        if note:
            res["note"] = note
        return res
    finally:
        if th:
            th.join()  # tsc reads files in work
        if lock:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- comparison
def _canon(x):
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, list):
        return [_canon(v) for v in x]
    return x


def _key(x):
    return json.dumps(_canon(x), sort_keys=True)


def deep_sort(x):
    if isinstance(x, list):
        return sorted((deep_sort(v) for v in x), key=_key)
    return x


def approx_eq(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(approx_eq(x, y) for x, y in zip(a, b))
    return a == b


def compare(cmp: str, got, exp) -> bool:
    if cmp == "unordered" and isinstance(got, list) and isinstance(exp, list):
        return approx_eq(sorted(got, key=_key), sorted(exp, key=_key))
    if cmp == "unordered_deep":
        return approx_eq(deep_sort(got), deep_sort(exp))
    return approx_eq(got, exp)
