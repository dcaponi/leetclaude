---
name: leetclaude
user-invocable: false
description: Tongue-in-cheek gate that makes the user solve a LeetCode problem sized to their request before Claude does code work, while Claude does the real work in the background. Use whenever a hook message says "LeetClaude is ON", or when the user asks to turn LeetClaude on or off, check its status or stats, tap out, or "leetclaude" a task.
---

# LeetClaude

The user installed this on purpose: coding interviews have nothing to do with the job, so now they are the job (and it keeps their skills sharp while you work). Play it straight: dry, brief, no lectures.

`LG` below means the `leetclaude` command. A plugin install puts it on your PATH. If the shell can't find it, use `${CLAUDE_SKILL_DIR}/../../bin/leetclaude`. Each command prints one short line. Don't read this plugin's files, fetch problems, or describe the problem to the user. The local page handles all of that, and it costs you zero tokens.

## A code request while LeetClaude is ON

1. **Tier the task by the real work involved, not by how it's phrased:**
   - `quiz`: rename, typo, comment- or docs-only edit, version bump, one-line config.
   - `easy`: a small change in one place (a button color, a log line, a constant, an obvious one-line bug).
   - `medium`: a feature or fix across a few files, a new endpoint, tests for a module, real debugging.
   - `hard`: a migration, a large refactor, a cross-cutting change, a new subsystem, or anything that needs real research.
   - Add `--sql` when the task is mainly about the database (schema, queries, DB migrations, ORM models).
   - Free of charge: questions, explanations, reading code, and fixing something you just got wrong (your bugs are on the house).
2. **Open a ticket** from the project root: `LG gate --tier <tier> --task "<summary, 10 words max>" [--sql]`. The repo's language is detected automatically. Pass `--lang` only if the user asks for one.
   - For `quiz`: if the project's architecture is already in your context, pass one question about it: `--quiz '{"q":"…","choices":["…","…","…","…"],"answer":<index>,"why":"…"}'`, or a written one: `{"q":"…","accept":["<regex>"],"answer":"…","why":"…"}`. Otherwise leave `--quiz` out and the bank supplies a question. Don't explore the repo just to write one.
3. **Tell the user in one line**, e.g. `LeetClaude: solve "Group Anagrams" (medium, Python) at http://127.0.0.1:4790/. I'm on it in the background.`
4. **Do the actual task in the background** so the user isn't stuck waiting. Launch a background `general-purpose` Agent with a complete, self-contained brief (goal, files, constraints, definition of done). If the whole task is a couple of tool calls, do it inline instead, because an agent costs more than it saves there.
5. **When the work finishes**, run `LG done` (the page then tells the user you're waiting on them) and report the result as you normally would.

The hook blocks the user's next prompt until they solve the problem or tap out on the page. It parks the blocked prompt on the page so nothing is lost. You never check solutions; the page does that. Don't solve, hint at, or discuss the current problem unless the user has tapped out.

## Commands

The user has slash commands for these: `/leetclaude:on`, `/leetclaude:off`, `/leetclaude:status`, `/leetclaude:stats`, `/leetclaude:bail`, `/leetclaude:open`, `/leetclaude:config`. If they ask in words instead, run the matching `LG <command>` (`on [--all]`, `off [--all]`, `status`, `stats`, `bail`, `open`, `config [--set key=value]`) and relay its output verbatim.

The page enforces the rules: trade one hard for two mediums, or one medium for two easies; tapping out reveals the answer and opens the gate; stats record solves, tap-outs, and trades per tier.
