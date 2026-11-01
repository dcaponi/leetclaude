"""Unit tests for leetclaude/runners.py: TypeScript type checking, Go import scan and panic locations, starters.

Run: python3 -m unittest tests/test_runners.py
Scratch runs go to $LEETCLAUDE_HOME (a temp dir if unset), never ~/.leetclaude.
"""
from __future__ import annotations

import atexit
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

if not os.environ.get("LEETCLAUDE_HOME"):
    _home = tempfile.mkdtemp(prefix="lg-test-home-")
    os.environ["LEETCLAUDE_HOME"] = _home
    atexit.register(shutil.rmtree, _home, True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leetclaude import runners  # noqa: E402

TWO_SUM = {"name": "twoSum", "params": [{"name": "nums", "type": "integer[]"}, {"name": "target", "type": "integer"}],
           "return": {"type": "integer[]"}}
TWO_SUM_TESTS = [[[2, 7, 11, 15], 9], [[3, 2, 4], 6]]
TWO_SUM_EXPECTED = [[0, 1], [1, 2]]
MERGE = {"name": "mergeTwoLists", "params": [{"name": "list1", "type": "ListNode"}, {"name": "list2", "type": "ListNode"}],
         "return": {"type": "ListNode"}}
INVERT = {"name": "invertTree", "params": [{"name": "root", "type": "TreeNode"}], "return": {"type": "TreeNode"}}

HAVE_NODE = runners.LANGS["typescript"].available()
HAVE_TSC = HAVE_NODE and shutil.which("tsc") is not None
HAVE_GO = runners.LANGS["go"].available()


def run(lang, meta, tests, code):
    return runners.run(lang, meta, tests, code)


def assert_passes(tc: unittest.TestCase, r: dict, expected: list):
    tc.assertEqual(r.get("status"), "ok", r)
    for i, exp in enumerate(expected):
        kind, got = r["results"][i]
        tc.assertEqual(kind, "ok", r)
        tc.assertTrue(runners.compare("exact", got, exp), (got, exp))


# ---------------------------------------------------------------- TypeScript
@unittest.skipUnless(HAVE_TSC, "tsc not on PATH")
class TypeScriptTypeCheck(unittest.TestCase):
    def test_type_error_is_compile_error_with_user_line(self):
        code = (runners.LANGS["typescript"].starter(MERGE).split("function")[0] +  # the starter's comment block
                "function twoSum(nums: number[], target: number): number[] {\n"
                "    const seen = new Map<number, number>();\n"
                "    let count: number = \"zero\";\n"
                "    return [0, 1];\n"
                "};\n")
        line = code.split("\n").index('    let count: number = "zero";') + 1
        r = run("typescript", TWO_SUM, TWO_SUM_TESTS, code)
        self.assertEqual(r["status"], "compile_error", r)
        msg = r["compile_error"]
        self.assertRegex(msg, rf"^solution\.ts\({line},9\): error TS2322: Type 'string' is not assignable to type 'number'\.")
        self.assertEqual(len(msg.strip().split("\n")), 1, msg)  # only the one real error
        self.assertNotIn("/", msg.split(":")[0])  # no scratch paths
        self.assertNotIn(os.environ["LEETCLAUDE_HOME"], msg)
        self.assertNotIn("note", r)

    def test_leetcode_style_loose_code_passes(self):
        # LeetCode compiles without strictNullChecks / noImplicitAny; ES2023 array methods and module-scoped
        # names that clash with DOM globals (name, close) must not be rejected.
        code = ("function twoSum(nums, target: number): number[] {\n"
                "    const name = 'x', close = 1;\n"
                "    let best: number = null;\n"
                "    const seen = {};\n"
                "    for (let i = 0; i < nums.length; i++) {\n"
                "        if (seen[target - nums[i]] !== undefined) return [seen[target - nums[i]], i].toSorted((a, b) => a - b);\n"
                "        seen[nums[i]] = i;\n"
                "    }\n"
                "    return [nums.findLastIndex(x => x === best)];\n"
                "}\n")
        r = run("typescript", TWO_SUM, TWO_SUM_TESTS, code)
        assert_passes(self, r, TWO_SUM_EXPECTED)
        self.assertNotIn("note", r)

    def test_listnode_solution_type_checks(self):
        code = runners.LANGS["typescript"].starter(MERGE).split("function")[0] + (
            "function mergeTwoLists(list1: ListNode | null, list2: ListNode | null): ListNode | null {\n"
            "    const dummy = new ListNode();\n"
            "    let tail: ListNode = dummy;\n"
            "    while (list1 && list2) {\n"
            "        if (list1.val <= list2.val) { tail.next = list1; list1 = list1.next; }\n"
            "        else { tail.next = list2; list2 = list2.next; }\n"
            "        tail = tail.next;\n"
            "    }\n"
            "    tail.next = list1 ?? list2;\n"
            "    return dummy.next;\n"
            "};\n")
        r = run("typescript", MERGE, [[[1, 2, 4], [1, 3, 4]], [[], [0]]], code)
        assert_passes(self, r, [[1, 1, 2, 3, 4, 4], [0]])
        self.assertNotIn("note", r)

    def test_treenode_solution_type_checks(self):
        code = runners.LANGS["typescript"].starter(INVERT).split("function")[0] + (
            "function invertTree(root: TreeNode | null): TreeNode | null {\n"
            "    if (root === null) return null;\n"
            "    const out = new TreeNode(root.val, invertTree(root.right), invertTree(root.left));\n"
            "    return out;\n"
            "};\n")
        r = run("typescript", INVERT, [[[4, 2, 7, 1, 3, 6, 9]], [[]]], code)
        assert_passes(self, r, [[4, 7, 2, 9, 6, 3, 1], []])

    def test_user_defined_listnode_does_not_clash(self):
        code = ("class ListNode {\n    val: number\n    next: ListNode | null\n"
                "    constructor(val?: number, next?: ListNode | null) { this.val = val ?? 0; this.next = next ?? null; }\n}\n"
                "function mergeTwoLists(a: ListNode | null, b: ListNode | null): ListNode | null {\n"
                "    if (!a) return b;\n    if (!b) return a;\n"
                "    if (a.val <= b.val) { a.next = mergeTwoLists(a.next, b); return a; }\n"
                "    b.next = mergeTwoLists(a, b.next);\n    return b;\n}\n")
        r = run("typescript", MERGE, [[[1, 2], [1, 3]]], code)
        assert_passes(self, r, [[1, 1, 2, 3]])

    def test_wrong_listnode_member_is_reported(self):
        code = ("function mergeTwoLists(list1: ListNode | null, list2: ListNode | null): ListNode | null {\n"
                "    return list1.nxt;\n"
                "}\n")
        r = run("typescript", MERGE, [[[1], [2]]], code)
        self.assertEqual(r["status"], "compile_error", r)
        self.assertTrue(r["compile_error"].startswith("solution.ts(2,18): error TS2"), r["compile_error"])


@unittest.skipUnless(HAVE_NODE, "node not on PATH")
class TypeScriptWithoutTsc(unittest.TestCase):
    def test_no_tsc_strips_types_and_sets_note(self):
        real_which = shutil.which
        with mock.patch.object(runners.shutil, "which", lambda name, *a, **k: None if name == "tsc" else real_which(name, *a, **k)):
            r = run("typescript", TWO_SUM, TWO_SUM_TESTS,
                    "function twoSum(nums: number[], target: number): number[] {\n"
                    "    let unchecked: number = 'a type error, but not checked';\n"
                    "    return target === 9 ? [0, 1] : [1, 2];\n}\n")
        assert_passes(self, r, TWO_SUM_EXPECTED)
        self.assertEqual(r["note"], "Type errors aren't checked: install TypeScript (npm i -g typescript) to enable it.")
        self.assertEqual(set(r) - {"note"}, {"status", "results", "stdout", "stderr", "ms", "exit"})


# ---------------------------------------------------------------- Go
class GoScan(unittest.TestCase):
    def test_code_only_blanks_literals_and_comments(self):
        src = ('a := "math.Max // not a comment" // fmt.Println "q"\n'
               "b := `strings.Split\nsort.Ints` + 'x' + '\\'' + '\"'\n"
               "/* heap.Init(h)\n */ c := math.Abs(1)\n")
        out = runners.go_code_only(src)
        self.assertEqual(out.count("\n"), src.count("\n"))
        for name in ("math.Max", "fmt.", "strings.", "sort.", "heap."):
            self.assertNotIn(name, out)
        self.assertIn("c := math.Abs(1)", out)


@unittest.skipUnless(HAVE_GO, "go not on PATH")
class GoRun(unittest.TestCase):
    def test_package_names_in_strings_and_comments_add_no_imports(self):
        code = ("// math.Max and fmt.Println appear only in this comment\n"
                "/* sort.Ints(nums) strings.Split */\n"
                "func twoSum(nums []int, target int) []int {\n"
                "    note := \"math.Max(a, b) and strconv.Itoa\"\n"
                "    raw := `fmt.Sprintf(\"%d\") sort.Slice`\n"
                "    quote := '\"'\n"
                "    _, _, _ = note, raw, quote\n"
                "    seen := map[int]int{}\n"
                "    for i, n := range nums {\n"
                "        if j, ok := seen[target-n]; ok {\n"
                "            return []int{j, i}\n"
                "        }\n"
                "        seen[n] = i\n"
                "    }\n"
                "    return nil\n"
                "}\n")
        r = run("go", TWO_SUM, TWO_SUM_TESTS, code)
        assert_passes(self, r, TWO_SUM_EXPECTED)

    def test_real_use_is_still_imported(self):
        code = ("func twoSum(nums []int, target int) []int {\n"
                "    _ = \"strings.Split\"\n"
                "    if int(math.Max(float64(target), 0)) == 9 {\n"
                "        return []int{0, 1}\n"
                "    }\n"
                "    return []int{1, 2}\n"
                "}\n")
        assert_passes(self, run("go", TWO_SUM, TWO_SUM_TESTS, code), TWO_SUM_EXPECTED)

    def test_panic_reports_solution_line(self):
        code = ("/**\n * a comment block\n */\n"
                "func pick(nums []int) int {\n"
                "    return nums[len(nums)+1]\n"  # line 5
                "}\n"
                "func twoSum(nums []int, target int) []int {\n"
                "    return []int{pick(nums)}\n"  # line 8
                "}\n")
        r = run("go", TWO_SUM, TWO_SUM_TESTS[:1], code)
        kind, msg = r["results"][0]
        self.assertEqual(kind, "err", r)
        self.assertIn("index out of range", msg)
        self.assertIn("\n  at solution.go:5 (pick)", msg)
        self.assertIn("\n  at solution.go:8 (twoSum)", msg)
        self.assertLess(msg.index("solution.go:5"), msg.index("solution.go:8"))  # innermost first
        self.assertNotRegex(msg, r"main\.go|/")

    def test_panic_line_with_own_package_clause(self):
        code = ("package main\n\nimport \"fmt\"\n\n"
                "func twoSum(nums []int, target int) []int {\n"
                "    var m map[int]int\n"
                "    m[target] = 1\n"  # line 7
                "    return []int{len(fmt.Sprint(m))}\n"
                "}\n")
        r = run("go", TWO_SUM, TWO_SUM_TESTS[:1], code)
        kind, msg = r["results"][0]
        self.assertEqual(kind, "err", r)
        self.assertTrue(msg.startswith("assignment to entry in nil map\n  at solution.go:7 (twoSum)"), msg)

    def test_explicit_panic_value(self):
        code = "func twoSum(nums []int, target int) []int {\n    panic(\"boom\")\n}\n"
        kind, msg = run("go", TWO_SUM, TWO_SUM_TESTS[:1], code)["results"][0]
        self.assertEqual((kind, msg), ("err", "boom\n  at solution.go:2 (twoSum)"))


# ---------------------------------------------------------------- starters
class Starters(unittest.TestCase):
    def test_rust_starter_shows_leetcode_impl_blocks(self):
        rs = runners.LANGS["rust"]
        lst = rs.starter(MERGE)
        self.assertIn("// impl ListNode {\n//   #[inline]\n//   fn new(val: i32) -> Self {\n//     ListNode {\n"
                      "//       next: None,\n//       val\n//     }\n//   }\n// }\nimpl Solution {", lst)
        tree = rs.starter(INVERT)
        self.assertIn("// impl TreeNode {\n//   #[inline]\n//   pub fn new(val: i32) -> Self {\n//     TreeNode {\n"
                      "//       val,\n//       left: None,\n//       right: None\n//     }\n//   }\n// }\nuse std::rc::Rc;", tree)
        for s in (lst, tree):  # all of the definition stays commented out
            head = s.split("impl Solution")[0]
            self.assertTrue(all(l.startswith("//") or l.startswith("use ") for l in head.strip().split("\n")), head)
        self.assertNotIn("impl ListNode", rs.starter(TWO_SUM))


if __name__ == "__main__":
    unittest.main()
