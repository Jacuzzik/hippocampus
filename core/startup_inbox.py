"""The start-up inbox: one Markdown file per agent, written when the app starts and when an agent's terminal starts.

It holds what the agent must know before it acts: its waiting messages, the agents it can message, how to send a message and how to report back.
"""

import json
from pathlib import Path
from typing import Any

from core import inbox


def file_for(hive: Path, agent: str) -> Path:
    """Where the agent's start-up inbox file lives: beside the hive, outside the app folder, so the agent can read it."""
    return hive.parent / "briefings" / f"{agent}-inbox.md"


def build(hive: Path, agent: str, agents: list[dict[str, Any]]) -> str:
    """The text of the agent's start-up inbox. Only the agent's own waiting messages are listed; the others are not shown to it."""
    lines = [f"# Start-up inbox for {agent}", "", "## Waiting messages"]
    waiting = inbox.pending(hive, agent)
    if waiting:
        # Only the headline: the app types each message in full right after this, so the body is not sent twice.
        for _, message in waiting:
            lines.append(f"- {message.get('act') or 'request'} from {message.get('from')}: {message.get('subject') or '(no subject)'}")
        lines.append("Each one is typed to you in full next. Act on each once.")
    else:
        lines.append("- None.")
    lines += ["", "## Agents you can message"]
    others = [a for a in agents if a.get("id") and a.get("id") != agent]
    if agent != "hippoherman":
        # The main agent is always someone a normal agent can report to.
        others.insert(0, {"id": "hippoherman", "name": "Hippoherman", "goal": "main agent: receives your reports"})
    if others:
        for other in others:
            goal = other.get("goal") or other.get("description") or "not described yet"
            lines.append(f"- {other.get('id')} ({other.get('name') or other.get('id')}): {goal}")
    else:
        lines.append("- None yet.")
    lines += [
        "",
        "## How to send a message",
        f"Your outbox folder is {hive / agent / 'outbox'}.",
        inbox.FORMAT_HELP,
        f"Example: {json.dumps(inbox.EXAMPLE)}",
        "The app checks it and moves it into the receiver's inbox. You send only as yourself.",
        "",
        "## How to report back",
        "When a task is done, blocked, or you need a decision, send one message to hippoherman.",
        "Start the subject with DONE:, BLOCKED: or QUESTION:, then say the task id, what changed and what is next.",
        "",
        "## Rules",
        "- Act on your waiting messages. Do not send a reply that only acknowledges.",
        "- Reply only when your work needs it.",
        "- Message hippoherman only when you genuinely need a decision.",
        "- Never message the user directly.",
    ]
    if agent == "hippoherman":
        lines += [
            "",
            "## Main agent reading of reports",
            "- Act on BLOCKED and QUESTION reports.",
            "- Note DONE reports without replying.",
        ]
    return "\n".join(lines) + "\n"


def for_chat(text: str, path: Path, limit: int = 1500) -> str:
    """The inbox as one line to type into a terminal. Agents on Claude cannot read files in the app folder, so the text itself is sent."""
    flat = " | ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(flat) > limit:
        flat = flat[:limit] + f" ...(full list: {path})"
    return f"Your start-up inbox: {flat}"


def write(hive: Path, agent: str, agents: list[dict[str, Any]]) -> Path:
    """Write the agent's start-up inbox file and return its path."""
    path = file_for(hive, agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(hive, agent, agents), encoding="utf-8")
    return path
