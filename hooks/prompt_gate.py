#!/usr/bin/env python3
"""UserPromptSubmit hook.

- Gate OFF for this project: do nothing.
- Ticket open: block the prompt (and park its text so it isn't lost). Its own commands (`/leetclaude:...`, `$leetcodex ...`) always pass.
- No ticket: inject a one-line reminder so Claude runs the leetclaude skill for code tasks.
Any internal error fails open (never wedge the user's session over a joke).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def _agent(data, detect_agent):
    """`--agent X` from the hook command wins; else Claude Code's env var; else Codex's turn_id field."""
    if "--agent" in sys.argv[1:-1]:
        return sys.argv[sys.argv.index("--agent") + 1]
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_CHILD_SESSION"):
        return "claude"
    if "turn_id" in data:
        return "codex"
    return detect_agent(argv0="")


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    from leetclaude.common import brand, cmd, detect_agent, is_enabled, load_config, locked_state, read_state, url

    cfg = load_config()
    cwd = data.get("cwd") or os.getcwd()
    if not is_enabled(cfg, cwd):
        return
    prompt = (data.get("prompt") or "").strip()
    if prompt.startswith(("/leetclaude", "$leetcodex", "/leetcodex", "leetcodex ")):
        return
    agent = _agent(data, detect_agent)
    b = brand(agent)
    st = read_state()
    t = st.get("ticket")
    if t:
        it = next((i for i in t["queue"] if i["status"] == "active"), {})
        with locked_state() as s:
            s["parked_prompt"] = {"text": prompt[:20000], "ts": time.time()}
        what = "a quiz" if it.get("kind") == "quiz" else f"{it.get('tier')} \"{it.get('title')}\""
        done = f" {b['agent_name']} already finished your last task. It's waiting on you." if t.get("task_done_at") else ""
        print(json.dumps({
            "decision": "block",
            "reason": (f"{b['name']}: ticket #{t['id']} is open. Solve {what} at {url(cfg)} (or tap out there) "
                       f"before prompting again. Your prompt is parked on that page.{done} "
                       f"Escape hatches: {cmd('bail', agent)}, {cmd('off', agent)}."),
        }))
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (f"{b['name']} is ON for this project. If this prompt asks you to write, change, or run code "
                              f"(not just answer a question), follow the {b['cli']} skill first: tier the task, run "
                              f"`{b['cli']} gate`, then do the work in the background."),
    }}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # fail open
        pass
