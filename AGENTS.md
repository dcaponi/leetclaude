# Notes for coding agents

- **Installing this for a user?** Follow [INSTALL.md](INSTALL.md) (Codex: the "If you are Codex" section).
- **Working on the code?**
  - Python is stdlib only and must run on Python 3.9 (the macOS system `python3`).
  - `ui/` is vanilla HTML/CSS/JS with no build step. Keep text colors at WCAG AA contrast (4.5:1) in both themes.
  - Tests: `python3 tests/run_lang_tests.py -j 4` (judge, 9 languages) and `python3 -m unittest tests/test_runners.py`.
  - After editing `bank_src/`, run `python3 scripts/build_bank.py`.
  - Set `LEETCLAUDE_HOME` to a scratch folder when you test, so you don't touch the user's stats in `~/.leetclaude`.
- The product is called LeetClaude under Claude Code and LeetCodex under Codex. `leetclaude/common.py` (`detect_agent`, `brand`) picks the name.
