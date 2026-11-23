"""Playbooks (N.22): a note format for a repeatable piece of work, and a runner.

A playbook is any note in the vault's "Playbooks" folder. Its title is the note's first heading and
its steps are its numbered or bulleted list items, in order; other text is kept as context. Running
one sends the steps to an agent as a single inbox message, so the agent works through them like any
other request and the run shows in the Inbox. Nothing runs without the user's click.
"""

import re
from pathlib import PurePosixPath
from typing import Any

FOLDER = "Playbooks"
STEP = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")
HEADING = re.compile(r"^#\s+(.+?)\s*$")
STEPS_MAX = 50


def is_playbook(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return len(parts) >= 2 and parts[0] == FOLDER and path.endswith(".md")


def parse(path: str, text: str) -> dict[str, Any]:
    title = PurePosixPath(path).stem
    steps: list[str] = []
    context: list[str] = []
    body = text
    if body.startswith("---\n"):
        end = body.find("\n---", 4)
        if end > 0:
            body = body[end + 4 :]
    for line in body.splitlines():
        heading = HEADING.match(line)
        if heading and not steps and title == PurePosixPath(path).stem:
            title = heading.group(1)
            continue
        step = STEP.match(line)
        if step:
            steps.append(step.group(1))
        elif line.strip() and not line.lstrip().startswith("#"):
            context.append(line.strip())
    return {"path": path, "title": title, "steps": steps[:STEPS_MAX], "context": context[:10]}


def message(playbook: dict[str, Any], extra: str = "") -> str:
    lines = [
        f"Run the playbook [[{playbook['path'].removesuffix('.md')}]]: {playbook['title']}.",
        "",
    ]
    if playbook["context"]:
        lines += [" ".join(playbook["context"])[:600], ""]
    lines += [f"{i}. {step}" for i, step in enumerate(playbook["steps"], 1)]
    if extra.strip():
        lines += ["", f"Also: {extra.strip()[:500]}"]
    lines += ["", "Work through the steps in order and report what you did for each."]
    return "\n".join(lines)
