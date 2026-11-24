"""The Claude Code PreToolUse hook for an agent that asks first (N.12).

Run as `python -m core.approval_hook <approvals folder> <agent>`. Claude Code sends the tool call as JSON on
stdin. A folder rule the user approved answers at once. Otherwise a request file is written and this waits for the
app's answer. If nobody answers in time, the answer is "ask", so Claude Code's own prompt takes over: a missing
answer never approves anything."""

import json
import sys
from pathlib import Path

from core import approvals


def decide(base: Path, agent: str, event: dict) -> tuple[str, str]:
    tool = str(event.get("tool_name", ""))
    spec = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    cwd = str(event.get("cwd", ""))
    if tool not in approvals.TOOLS:
        return "ask", "not a tool this hook handles"
    command = str(spec.get("command", ""))
    if any(approvals.matches(rule, tool, cwd, command) for rule in approvals.rules(base)):
        return "allow", "approved earlier for this folder"
    rid = approvals.request(base, agent, tool, cwd, spec)
    try:
        decision = approvals.wait_for(base, rid)
    finally:
        approvals.finish(base, rid)
    if decision in ("once", "folder"):
        return "allow", "approved in Hippocampus"
    if decision == "deny":
        return "deny", "denied in Hippocampus"
    return "ask", "no answer in Hippocampus yet"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return 2
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    verdict, reason = decide(Path(argv[0]), argv[1], event if isinstance(event, dict) else {})
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": verdict,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
