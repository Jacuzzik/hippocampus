"""One-click handoff (N.06): a handoff note shared with the inbox.

The note is written into the vault's "Handoffs" folder and the receiving agent gets an inbox message
whose body is the same text plus a link to the note, so the agent reads it where it already reads its
work, and the note stays in the vault's memory. Its parts are what the app holds: the user's own
words, the giving agent's open tasks, its recent tool calls (from its session file) and its pinned
notes. No model is called.
"""

from datetime import datetime
from typing import Any

FOLDER = "Handoffs"
NOTE_MAX = 2000
CALLS = 10


def path_for(when: datetime, giver: str, taker: str) -> str:
    return f"{FOLDER}/{when.strftime('%Y-%m-%d %H%M')} {giver} to {taker}.md"


def compose(
    when: datetime,
    giver: str,
    taker: str,
    note: str,
    tasks: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    pins: list[str],
) -> str:
    lines = [f"# Handoff from {giver} to {taker}", "", f"{when.strftime('%Y-%m-%d %H:%M')}", ""]
    lines += ["## What to pick up", "", note.strip()[:NOTE_MAX] or "No note was written.", ""]
    lines += ["## Open tasks", ""]
    if tasks:
        for task in tasks:
            lines.append(f"- {task.get('id')} {task.get('title', '')} ({task.get('status')})")
    else:
        lines.append(f"- None assigned to {giver}.")
    lines += ["", "## Last tool calls", ""]
    if calls:
        for call in calls[:CALLS]:
            detail = str(call.get("detail") or "").replace("\n", " ")[:160]
            lines.append(f"- {call.get('tool')} ({call.get('status')}): {detail}")
    else:
        lines.append("- None recorded.")
    lines += ["", "## Pinned notes", ""]
    lines += [f"- [[{pin.removesuffix('.md')}]]" for pin in pins] or ["- None."]
    return "\n".join(lines).rstrip() + "\n"
