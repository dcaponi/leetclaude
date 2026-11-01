# Installing LeetClaude / LeetCodex (instructions for coding agents)

You are probably Claude Code or Codex, and the user asked you to install this. Follow the section for the agent you are. Run each step, check its result, and stop and tell the user if a check fails. Don't edit the user's projects.

Requirements: `git`, and `python3` 3.9 or newer (`python3 --version`). Nothing else is installed: the tool is stdlib Python plus a static web page.

## If you are Claude Code: install the plugin

1. Run: `claude plugin install leetclaude --marketplace dcaponi/leetclaude --scope user`
   - If that fails with an unknown-option error (Claude Code older than 2.1.292), run instead:
     `claude plugin marketplace add dcaponi/leetclaude` and then `claude plugin install leetclaude@leetclaude --scope user`
2. Check: `claude plugin list` shows `leetclaude@leetclaude` as enabled.
3. Tell the user: "Run `/reload-plugins` (or restart Claude Code), then `/leetclaude:on` in a project to turn the gate on there."

The plugin carries the skill, the slash commands (`/leetclaude:on`, `:off`, `:status`, `:stats`, `:bail`, `:open`, `:config`), the `UserPromptSubmit` hook, and the `leetclaude` CLI. You do not need to edit `~/.claude/settings.json`.

## If you are Codex: clone and run the installer

1. Clone or update (this writes outside the workspace, so request escalated permissions):
   - New: `git clone https://github.com/dcaponi/leetclaude ~/.local/share/leetclaude`
   - Already there: `git -C ~/.local/share/leetclaude pull --ff-only`
2. Run: `~/.local/share/leetclaude/install.sh --codex` (escalated; it writes to `~/.agents/skills`, `~/.codex/hooks.json`, and `~/.codex/rules/`).
3. Check:
   - `ls -l ~/.agents/skills/leetcodex/SKILL.md` exists.
   - `~/.codex/hooks.json` has a `UserPromptSubmit` entry that runs `hooks/prompt_gate.py --agent codex`. The installer keeps the user's other hooks and writes a backup next to the file.
   - `~/.agents/skills/leetcodex/scripts/leetcodex --help` prints usage that starts with `usage: leetcodex`.
4. Tell the user, in this order:
   - "Start a new Codex session (skills and rules load at startup)."
   - "Run `/hooks` and trust the LeetCodex hook. Codex asks once for any new hook."
   - "Type `$leetcodex on` in a project to turn the gate on there."

What the rules file does: `~/.codex/rules/leetcodex.rules` allows the exact path of the `leetcodex` CLI to run outside the sandbox without a prompt, because the CLI keeps state in `~/.leetclaude`, serves a page on `127.0.0.1:4790`, opens the browser, and fetches problems from leetcode.com. It allows only that path.

## Both agents on one machine

From a clone: `./install.sh` (it installs for every agent it finds on PATH). Then do the "tell the user" steps for each agent.

## Uninstall

`./uninstall.sh` from the clone (or `~/.local/share/leetclaude/uninstall.sh`). It removes the plugin, the Codex skill link, hook, and rules, and keeps the user's stats in `~/.leetclaude`. Under Claude Code alone, `claude plugin uninstall leetclaude@leetclaude` is enough.

## Troubleshooting

- The page doesn't open: run `leetclaude open` (Claude) or `$leetcodex open` (Codex), or browse to http://127.0.0.1:4790/.
- Port 4790 is taken: `leetclaude config --set port=4791`.
- No browser tab wanted: `leetclaude config --set open_browser=false`.
- Offline: `leetclaude config --set source="bank"` uses only the curated problems.
