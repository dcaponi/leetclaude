#!/usr/bin/env bash
# Removes LeetClaude (Claude Code plugin) and LeetCodex (Codex skill, hook, rules). Keeps ~/.leetclaude (your stats).
set -euo pipefail
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
if command -v claude >/dev/null 2>&1; then
  claude plugin uninstall leetclaude@leetclaude >/dev/null 2>&1 && echo "Claude Code: plugin removed" || echo "Claude Code: plugin not installed"
  claude plugin marketplace remove leetclaude >/dev/null 2>&1 && echo "Claude Code: marketplace removed" || true
fi
[ -L "$HOME/.agents/skills/leetcodex" ] && rm "$HOME/.agents/skills/leetcodex" && echo "Codex: skill link removed"
rm -f "$CODEX_DIR/rules/leetcodex.rules"
if [ -f "$CODEX_DIR/hooks.json" ]; then
  python3 - "$CODEX_DIR/hooks.json" <<'PY'
import json, os, sys
path = sys.argv[1]
with open(path) as f:
    cfg = json.load(f)
groups = cfg.get("hooks", {}).get("UserPromptSubmit", [])
keep = [g for g in groups if not any("hooks/prompt_gate.py" in h.get("command", "") for h in g.get("hooks", []))]
if len(keep) != len(groups):
    cfg["hooks"]["UserPromptSubmit"] = keep
    if not keep:
        del cfg["hooks"]["UserPromptSubmit"]
    with open(path + ".tmp", "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    os.replace(path + ".tmp", path)
    print("Codex: hook removed")
PY
fi
for b in leetclaude leetcodex; do [ -L "$HOME/.local/bin/$b" ] && rm "$HOME/.local/bin/$b"; done
echo "Done. Your stats are still in ~/.leetclaude (delete that folder to forget everything)."
