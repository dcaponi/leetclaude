---
name: leetcodex
description: Tongue-in-cheek gate that makes the user solve a LeetCode problem sized to their request before Codex does code work, while Codex does the real work. Use whenever a hook message says "LeetCodex is ON", when the user types $leetcodex (on, off, status, stats, bail, open, config), or asks to turn LeetCodex on or off.
---

# LeetCodex

The user installed this on purpose: coding interviews have nothing to do with the job, so now they are the job (and it keeps their skills sharp while you work). Play it straight: dry, brief, no lectures.

`LG` below means `scripts/leetcodex` in this skill's folder. Run it by its absolute path. Each command prints one short line. Don't read this skill's other files, fetch problems, or describe the problem to the user. The local page handles all of that, and it costs you zero tokens.

**Sandbox:** LG keeps its state in `~/.leetclaude`, serves a page on `127.0.0.1:4790`, opens the browser, and fetches problems from leetcode.com, so it must run outside the sandbox. The installer adds an allow rule for LG's absolute path (`~/.agents/skills/leetcodex/scripts/leetcodex`, expanded), so call it exactly by that path and it runs unprompted. If a command still fails with a sandbox error (permission denied under `~/.leetclaude`, can't bind the port), run it again with escalated permissions (justification: "LeetCodex keeps state in ~/.leetclaude and serves a local page").

## A code request while LeetCodex is ON

1. **Tier the task by the real work involved, not by how it's phrased:**
   - `quiz`: rename, typo, comment- or docs-only edit, version bump, one-line config.
   - `easy`: a small change in one place (a button color, a log line, a constant, an obvious one-line bug).
   - `medium`: a feature or fix across a few files, a new endpoint, tests for a module, real debugging.
   - `hard`: a migration, a large refactor, a cross-cutting change, a new subsystem, or anything that needs real research.
   - Add `--sql` when the task is mainly about the database (schema, queries, DB migrations, ORM models).
   - Free of charge: questions, explanations, reading code, and fixing something you just got wrong (your bugs are on the house).
2. **Open a ticket** from the project root before you change anything: `LG gate --tier <tier> --task "<summary, 10 words max>" [--sql]`. The repo's language is detected automatically. Pass `--lang` only if the user asks for one.
   - For `quiz`: if the project's architecture is already in your context, pass one question about it: `--quiz '{"q":"…","choices":["…","…","…","…"],"answer":<index>,"why":"…"}'`, or a written one: `{"q":"…","accept":["<regex>"],"answer":"…","why":"…"}`. Otherwise leave `--quiz` out and the bank supplies a question. Don't explore the repo just to write one.
3. **Tell the user in one line**, e.g. `LeetCodex: solve "Group Anagrams" (medium, Python) at http://127.0.0.1:4790/. I'm on it.`
4. **Then do the task as you normally would.** The user solves the problem in the browser while you work.
5. **When the work is done**, run `LG done` (the page then tells the user you're waiting on them) and report the result as you normally would.

The prompt hook blocks the user's next prompt until they solve the problem or tap out on the page. It parks the blocked prompt on the page so nothing is lost. You never check solutions; the page does that. Don't solve, hint at, or discuss the current problem unless the user has tapped out.

## `$leetcodex <command>`

When the user types `$leetcodex on|off|status|stats|bail|open|config`, run `LG <command>` with the same arguments (`on --all`, `off --all`, `config --set source="bank"`) and relay its output verbatim. Nothing else.

The page enforces the rules: trade one hard for two mediums, or one medium for two easies; tapping out reveals the answer and opens the gate; stats record solves, tap-outs, and trades per tier.
