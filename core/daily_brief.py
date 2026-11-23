"""The daily brief note (N.09): one note a day in the vault's "Daily briefs" folder, written by the
scheduled job "Daily brief note" (off until the user turns it on, under Settings, Triggers).

It is made only from what the app already holds: today's calendar events, the task board, the
agents' status from the fleet rows, the user's unread messages and yesterday's activity. No model is
called, so it costs no tokens. Running it again on the same day rewrites that day's note.
"""

from collections import Counter
from datetime import date
from typing import Any

FOLDER = "Daily briefs"
STATUS_ORDER = ("doing", "blocked", "todo", "done")


def path_for(day: date) -> str:
    return f"{FOLDER}/{day.isoformat()}.md"


def compose(
    day: date,
    events: list[dict[str, str]],
    tasks: list[dict[str, Any]],
    agents: list[dict[str, Any]],
    unread: int,
    activity: list[dict[str, Any]],
) -> str:
    lines = [f"# Daily brief {day.isoformat()}", "", "Linked to [[Summaries]].", ""]

    lines += ["## Today", ""]
    today = [e for e in events if e.get("date") == day.isoformat()]
    if today:
        for event in today:
            when = event.get("time") or "all day"
            lines.append(f"- {when} {event.get('title', '')} ({event.get('status', '')})")
    else:
        lines.append("- Nothing on the calendar.")
    later = [e for e in events if e.get("date", "") > day.isoformat()][:3]
    for event in later:
        lines.append(f"- Next: {event.get('date')} {event.get('title', '')}")
    lines.append("")

    lines += ["## Tasks", ""]
    counts = Counter(str(t.get("status")) for t in tasks)
    if tasks:
        lines.append("- " + ", ".join(f"{counts[s]} {s}" for s in STATUS_ORDER if counts[s]) + ".")
        waiting = [t for t in tasks if t.get("waiting")]
        for task in waiting[:5]:
            lines.append(f"- Waiting on you: {task.get('id')} {task.get('title', '')}")
        for task in [t for t in tasks if t.get("status") == "doing"][:5]:
            who = task.get("assignee") or "nobody"
            lines.append(f"- Doing: {task.get('id')} {task.get('title', '')} ({who})")
    else:
        lines.append("- No tasks on the board.")
    lines.append("")

    lines += ["## Agents", ""]
    for agent in agents:
        extra = []
        if agent.get("inbox"):
            extra.append(f"{agent['inbox']} waiting in its inbox")
        if agent.get("breaker") and agent["breaker"] != "healthy":
            extra.append(f"circuit breaker {agent['breaker']}")
        tail = f": {', '.join(extra)}" if extra else ""
        lines.append(f"- {agent.get('name')} is {agent.get('status')}{tail}.")
    lines.append("")

    lines += ["## Messages", "", f"- {unread} unread for you in the Inbox.", ""]

    kinds = Counter(str(row.get("kind")) for row in activity)
    lines += ["## Yesterday", ""]
    if activity:
        lines.append("- " + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())) + ".")
        errors = [row for row in activity if row.get("kind") == "error"][:3]
        for row in errors:
            lines.append(f"- Error: {str(row.get('text', ''))[:160]}")
    else:
        lines.append("- No activity.")
    return "\n".join(lines).rstrip() + "\n"
