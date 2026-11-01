#!/usr/bin/env bash
# Installs LeetClaude for Claude Code and/or LeetCodex for Codex from this clone. Safe to re-run.
# Usage: ./install.sh [--claude] [--codex]     (no flags: every agent found on PATH)
# Nothing changes in a project until you turn it on there: /leetclaude:on (Claude Code) or $leetcodex on (Codex).
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
want_claude=0; want_codex=0
for a in "$@"; do
  case "$a" in
    --claude) want_claude=1 ;;
    --codex) want_codex=1 ;;
    -h|--help) sed -n 2,4p "$0"; exit 0 ;;
    *) echo "unknown option: $a (use --claude and/or --codex)" >&2; exit 2 ;;
  esac
done
if [ "$want_claude$want_codex" = "00" ]; then
  command -v claude >/dev/null 2>&1 && want_claude=1
  command -v codex >/dev/null 2>&1 && want_codex=1
  if [ "$want_claude$want_codex" = "00" ]; then
    echo "Found neither claude nor codex on PATH. Pass --claude or --codex." >&2; exit 1
  fi
fi
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null || { echo "Needs python3 3.9 or newer." >&2; exit 1; }
chmod +x "$REPO/bin/leetclaude" "$REPO/hooks/prompt_gate.py"
[ -f "$REPO/bank/bank.json" ] || python3 "$REPO/scripts/build_bank.py" >/dev/null

if [ "$want_claude" = 1 ]; then
  echo "Claude Code (LeetClaude):"
  if claude plugin marketplace add "$REPO" >/dev/null 2>&1; then
    echo "  marketplace: added $REPO"
  else
    claude plugin marketplace update leetclaude >/dev/null 2>&1 || true
    echo "  marketplace: already added (updated)"
  fi
  claude plugin install leetclaude@leetclaude --scope user >/dev/null && echo "  plugin:      leetclaude installed (user scope)"
  echo "  next:        restart Claude Code (or run /reload-plugins), then /leetclaude:on in a project"
fi

if [ "$want_codex" = 1 ]; then
  echo "Codex (LeetCodex):"
  mkdir -p "$HOME/.agents/skills"
  if [ -e "$HOME/.agents/skills/leetcodex" ] && [ ! -L "$HOME/.agents/skills/leetcodex" ]; then
    echo "  refusing to replace $HOME/.agents/skills/leetcodex (exists and is not a symlink)" >&2; exit 1
  fi
  ln -sfn "$REPO/codex/skills/leetcodex" "$HOME/.agents/skills/leetcodex"
  echo "  skill:       ~/.agents/skills/leetcodex -> $REPO/codex/skills/leetcodex"
  mkdir -p "$CODEX_DIR"
  python3 - "$CODEX_DIR/hooks.json" "$REPO" <<'PY'
import json, os, shutil, sys, time
path, repo = sys.argv[1], sys.argv[2]
cmd = f'python3 "{repo}/hooks/prompt_gate.py" --agent codex'
cfg = {}
if os.path.exists(path):
    with open(path) as f:
        cfg = json.load(f)
    shutil.copy2(path, f"{path}.bak-leetcodex-{int(time.time())}")
groups = cfg.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
groups[:] = [g for g in groups if not any("hooks/prompt_gate.py" in h.get("command", "") for h in g.get("hooks", []))]
groups.append({"hooks": [{"type": "command", "command": cmd, "timeout": 10}]})
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
print(f"  hook:        UserPromptSubmit -> prompt_gate.py in {path}")
PY
  mkdir -p "$CODEX_DIR/rules"
  cat > "$CODEX_DIR/rules/leetcodex.rules" <<RULES
# LeetCodex: run the installed leetcodex CLI outside the sandbox without asking each time.
# It keeps state in ~/.leetclaude, serves a page on 127.0.0.1, opens the browser, and fetches problems from leetcode.com.
# Exact paths only: a bare "leetcodex" pattern would also match any executable with that name.
prefix_rule(pattern = ["$HOME/.agents/skills/leetcodex/scripts/leetcodex"], decision = "allow", justification = "LeetCodex local gate")
prefix_rule(pattern = ["$REPO/codex/skills/leetcodex/scripts/leetcodex"], decision = "allow", justification = "LeetCodex local gate")
RULES
  echo "  rules:       $CODEX_DIR/rules/leetcodex.rules"
  echo "  next:        start a new Codex session (rules load at startup), run /hooks and trust the LeetCodex hook,"
  echo "               then type: \$leetcodex on"
fi

if [ -d "$HOME/.local/bin" ] && case ":$PATH:" in *":$HOME/.local/bin:"*) true ;; *) false ;; esac; then
  ln -sfn "$REPO/bin/leetclaude" "$HOME/.local/bin/leetclaude"
  ln -sfn "$REPO/bin/leetcodex" "$HOME/.local/bin/leetcodex"
  echo "CLI: ~/.local/bin/leetclaude and leetcodex"
fi
echo "Stats and state live in ~/.leetclaude. ./uninstall.sh removes everything except that folder."
