"""Guess the repository's primary language so problems are solved in it."""
from __future__ import annotations

import os
from collections import Counter

from . import runners

EXT = {".py": "python", ".ipynb": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
       ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript", ".svelte": "typescript", ".vue": "javascript",
       ".rb": "ruby", ".go": "go", ".java": "java", ".kt": "java", ".scala": "java", ".cpp": "cpp", ".cc": "cpp",
       ".cxx": "cpp", ".hpp": "cpp", ".c": "cpp", ".h": "cpp", ".rs": "rust", ".cs": "csharp"}
MARKERS = {"tsconfig.json": ("typescript", 40), "deno.json": ("typescript", 40), "package.json": ("javascript", 15),
           "go.mod": ("go", 40), "Cargo.toml": ("rust", 40), "pyproject.toml": ("python", 30), "requirements.txt": ("python", 25),
           "setup.py": ("python", 25), "Pipfile": ("python", 25), "uv.lock": ("python", 25), "Gemfile": ("ruby", 40),
           "pom.xml": ("java", 40), "build.gradle": ("java", 40), "build.gradle.kts": ("java", 40), "CMakeLists.txt": ("cpp", 30)}
SKIP = {"node_modules", ".git", ".venv", "venv", "env", "__pycache__", "dist", "build", "target", "vendor", ".next",
        "out", "bin", "obj", ".idea", ".vscode", "Pods", ".terraform", "site-packages", ".tox", ".mypy_cache", "coverage"}


def detect(root: str) -> tuple[str, str]:
    """Return (language key, short reason). Falls back to python when nothing supported is found."""
    score: Counter = Counter()
    for name, (lang, w) in MARKERS.items():
        if os.path.exists(os.path.join(root, name)):
            score[lang] += w
    try:
        for f in os.listdir(root):
            if f.endswith((".csproj", ".sln")):
                score["csharp"] += 40
    except OSError:
        pass
    n = 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        if dirpath[len(root):].count(os.sep) > 6:
            dirs[:] = []
        for f in files:
            lang = EXT.get(os.path.splitext(f)[1])
            if lang:
                score[lang] += 1
            n += 1
        if n > 5000:
            break
    if score.get("typescript") and score.get("javascript") and os.path.exists(os.path.join(root, "tsconfig.json")):
        score["typescript"] += score.pop("javascript")
    for lang, _ in score.most_common():
        if runners.LANGS[lang].available():
            return lang, f"detected {runners.LANGS[lang].label}"
    if score:
        top = score.most_common(1)[0][0]
        return "python", f"{runners.LANGS[top].label} toolchain missing; using Python"
    return "python", "no supported language found; using Python (LeetCode has no HCL/YAML track)"
