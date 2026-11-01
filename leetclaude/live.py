"""LeetCode GraphQL client (unofficial public endpoint): random problems, statements, community answers."""
from __future__ import annotations

import html as _html
import json
import random
import re
import urllib.error
import urllib.request

from .common import CACHE_DIR, ensure_home
from . import runners

GQL = "https://leetcode.com/graphql"
HEADERS = {"Content-Type": "application/json", "Referer": "https://leetcode.com/problemset/",
           "User-Agent": "Mozilla/5.0 (LeetClaude; personal practice tool)"}
TIER_TO_LC = {"easy": "EASY", "medium": "MEDIUM", "hard": "HARD"}
FENCE_ALIASES = {
    "python": {"python", "python3", "py"}, "javascript": {"javascript", "js"}, "typescript": {"typescript", "ts"},
    "java": {"java"}, "cpp": {"cpp", "c++"}, "go": {"go", "golang"}, "rust": {"rust", "rs"}, "ruby": {"ruby", "rb"},
    "csharp": {"csharp", "c#", "cs"}, "sql": {"mysql", "sql", "postgresql", "sqlite"},
}
LANG_TAG = {"python": "python3", "javascript": "javascript", "typescript": "typescript", "java": "java", "cpp": "cpp",
            "go": "golang", "rust": "rust", "ruby": "ruby", "csharp": "csharp", "sql": "mysql"}
MULTI_ANSWER = re.compile(r"(return any|any of them|if there are multiple|any valid|multiple valid|any possible|"
                          r"there may be multiple|you may return any|any one of)", re.I)


class LiveError(Exception):
    pass


def gql(query: str, variables: dict, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(GQL, data=json.dumps({"query": query, "variables": variables}).encode(), headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        raise LiveError(f"leetcode.com unreachable: {e}") from e
    if body.get("errors"):
        raise LiveError(body["errors"][0].get("message", "graphql error"))
    return body.get("data") or {}


Q_RANDOM = """query r($categorySlug: String, $filters: QuestionListFilterInput) {
  randomQuestion(categorySlug: $categorySlug, filters: $filters) { titleSlug } }"""
Q_QUESTION = """query q($s: String!) { question(titleSlug: $s) {
  questionFrontendId title titleSlug difficulty isPaidOnly content exampleTestcases metaData topicTags { slug } } }"""
Q_SOLUTIONS = """query a($questionSlug: String!, $first: Int, $orderBy: ArticleOrderByEnum, $tagSlugs: [String!]) {
  ugcArticleSolutionArticles(questionSlug: $questionSlug, first: $first, orderBy: $orderBy, tagSlugs: $tagSlugs) {
    edges { node { title topicId slug } } } }"""
Q_TOPIC = "query b($topicId: Int!) { topic(id: $topicId) { title post { content } } }"


def question(slug: str, use_cache: bool = True) -> dict:
    ensure_home()
    path = CACHE_DIR / "lc" / f"{slug}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text())
    q = gql(Q_QUESTION, {"s": slug}).get("question")
    if not q:
        raise LiveError(f"no such problem: {slug}")
    path.write_text(json.dumps(q))
    return q


def sanitize_html(h: str) -> str:
    h = re.sub(r"<(script|style|iframe|object|embed)\b.*?</\1\s*>", "", h or "", flags=re.S | re.I)
    h = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", h, flags=re.I)
    h = re.sub(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", r'\1="#"', h, flags=re.I)
    return h


def html_text(h: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    s = re.sub(r"</(p|div|pre|li|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return _html.unescape(s).replace("\xa0", " ")


def example_outputs(content: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"Output\s*:\s*\n?\s*([^\n]+)", html_text(content))]


def ascii_tables(content: str) -> list[dict | None]:
    t = html_text(content)
    out = []
    for m in re.finditer(r"Output\s*:", t):
        tbl, started = [], False
        for ln in t[m.end():].split("\n"):
            s = ln.strip()
            if s.startswith(("+", "|")):
                tbl.append(s)
                started = True
            elif started or s:
                break
        rows = [[c.strip() for c in r.strip("|").split("|")] for r in tbl if r.startswith("|")]
        if not rows:
            out.append(None)
            continue
        out.append({"cols": rows[0], "rows": [[None if c.lower() == "null" else c for c in r] for r in rows[1:]]})
    return out


def _base(slug, q, tier, kind):
    return {"pid": f"lc:{slug}", "slug": slug, "lc": q.get("questionFrontendId"), "title": q.get("title") or slug,
            "tier": tier, "kind": kind, "source": "live", "url": f"https://leetcode.com/problems/{slug}/",
            "tags": [t["slug"] for t in q.get("topicTags") or []]}


def build_algo(slug: str, q: dict, tier: str) -> dict:
    meta = json.loads(q.get("metaData") or "{}")
    if not meta or any(k in meta for k in ("systemdesign", "classname", "manual")) or meta.get("manual"):
        raise LiveError("design/manual problem")
    if not runners.meta_supported(meta):
        raise LiveError("unsupported types")
    content = q.get("content") or ""
    if MULTI_ANSWER.search(html_text(content)):
        raise LiveError("multiple valid answers")
    lines = [l for l in (q.get("exampleTestcases") or "").split("\n") if l.strip()]
    n = len(meta["params"])
    if n == 0 or len(lines) % n:
        raise LiveError("can't split examples")
    try:
        inputs = [[json.loads(l) for l in lines[i:i + n]] for i in range(0, len(lines), n)]
        outs = [json.loads(o) for o in example_outputs(content)]
    except json.JSONDecodeError as e:
        raise LiveError(f"unparseable example: {e}") from e
    if len(outs) != len(inputs) or not inputs:
        raise LiveError("examples/outputs mismatch")
    p = _base(slug, q, tier, "algo")
    p.update(meta=meta, cmp="unordered_deep" if re.search(r"any order", html_text(content), re.I) else "exact",
             tests=[{"args": a, "expected": e} for a, e in zip(inputs, outs)], examples=len(inputs))
    return p


def build_sql(slug: str, q: dict, tier: str) -> dict:
    meta = json.loads(q.get("metaData") or "{}")
    if not meta.get("database") or not meta.get("mysql"):
        raise LiveError("not a SQL problem")
    content = q.get("content") or ""
    datasets = [json.loads(l) for l in (q.get("exampleTestcases") or "").split("\n") if l.strip()]
    tables = ascii_tables(content)
    if not datasets or len(tables) != len(datasets) or any(t is None for t in tables):
        raise LiveError("can't parse expected tables")
    from . import sqlrun
    for ds in datasets:  # schema + data must load in SQLite
        sqlrun.build_db(meta["mysql"], ds).close()
    p = _base(slug, q, tier, "sql")
    text = html_text(content).lower()
    p.update(schema=meta["mysql"], datasets=datasets, expected=tables, examples=len(datasets),
             ordered=bool(re.search(r"(ordered|sorted|order) by\b", text) and "any order" not in text))
    return p


def random_problem(tier: str, kind: str, seen: set[str], tries: int = 8, ok=lambda p: True) -> dict | None:
    ensure_home()
    cat = "database" if kind == "sql" else "algorithms"
    for _ in range(tries):
        try:
            slug = gql(Q_RANDOM, {"categorySlug": cat, "filters": {"difficulty": TIER_TO_LC[tier]}})["randomQuestion"]["titleSlug"]
            if f"lc:{slug}" in seen:
                continue
            q = question(slug)
            if q.get("isPaidOnly") or not q.get("content"):
                continue
            p = build_sql(slug, q, tier) if kind == "sql" else build_algo(slug, q, tier)
            if not ok(p):
                continue
            (CACHE_DIR / "live" / f"{slug}.json").write_text(json.dumps(p))
            return p
        except LiveError as e:
            if "unreachable" in str(e):
                return None
            continue
        except (KeyError, TypeError, ValueError):
            continue
    return None


def load_live(slug: str) -> dict | None:
    path = CACHE_DIR / "live" / f"{slug}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _code_blocks(md: str):
    for m in re.finditer(r"```([^\n]*)\n(.*?)```", md, re.S):
        fence = m.group(1).strip().lower().replace("[]", "").split(" ")[0].strip()
        yield fence, m.group(2).rstrip()


LOOKS = {  # unlabeled fences: guess the language from the code's shape
    "python": r"^\s*(class Solution:|def \w+\(self)", "go": r"^\s*func \w+\(", "rust": r"impl Solution|pub fn \w+\(",
    "java": r"public \S+ \w+\(.*\)\s*\{", "cpp": r"public:\s*$|vector<", "csharp": r"public \S+ [A-Z]\w*\(",
    "javascript": r"(var|const|let) \w+ = function|^\s*function \w+\(", "typescript": r"function \w+\(.*:\s*\w+.*\)\s*:",
    "ruby": r"^\s*def \w+\(?[^)]*\)?\s*$(?![\s\S]*\bself\b)", "sql": r"(?i)^\s*(select|with)\b",
}


def _unescape(md: str) -> str:
    if md.count("\n") >= 3 or "\\n" not in md:
        return md
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "r": ""}.get(m.group(1), m.group(1)), md)


def _pick(md: str, lang: str) -> str | None:
    blocks = list(_code_blocks(_unescape(md)))
    for fence, code in blocks:
        if fence in FENCE_ALIASES.get(lang, {lang}):
            return code
    rx = LOOKS.get(lang)
    for fence, code in blocks:
        if not fence and rx and re.search(rx, code, re.M):
            if lang == "javascript" and re.search(LOOKS["typescript"], code, re.M):
                continue
            return code
    return None


def community_solution(slug: str, lang: str) -> dict | None:
    """Top-voted community answer in lang (falls back to python3). Zero model tokens: plain HTTP."""
    want = [lang] + (["python"] if lang not in ("python", "sql") else [])
    for lk in want:
        try:
            edges = gql(Q_SOLUTIONS, {"questionSlug": slug, "first": 5, "orderBy": "MOST_VOTES",
                                      "tagSlugs": [LANG_TAG.get(lk, lk)]})["ugcArticleSolutionArticles"]["edges"]
        except (LiveError, KeyError, TypeError):
            return None
        for e in edges:
            node = e["node"]
            try:
                t = gql(Q_TOPIC, {"topicId": int(node["topicId"])})["topic"]
            except (LiveError, KeyError, TypeError, ValueError):
                continue
            code = _pick((t.get("post") or {}).get("content") or "", lk)
            if code:
                return {"lang": lk, "code": code, "title": node.get("title", ""),
                        "url": f"https://leetcode.com/problems/{slug}/solutions/{node['topicId']}/{node.get('slug', '')}/"}
    return None


def statement(slug: str) -> str | None:
    try:
        return sanitize_html(question(slug).get("content") or "") or None
    except LiveError:
        return None
