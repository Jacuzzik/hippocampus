"""Task messages between agents. Each agent has an inbox and an outbox folder under the app's hive folder.

A task is one JSON file. The app types a received message into the receiver's terminal, then moves the file to .done.
An agent replies by writing a JSON file into its own outbox; the app moves it to the receiver's inbox.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any


def _folder(base: Path, agent: str, name: str) -> Path:
    if not agent or "/" in agent or "\\" in agent or agent.startswith("."):
        raise ValueError("Use an agent id without slashes.")
    path = base / agent / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, message: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(message), encoding="utf-8")
    tmp.replace(path)


def send(base: Path, sender: str, to: str, subject: str, body: str) -> str:
    """Put one message in the receiver's inbox and return its id."""
    message = {"id": uuid.uuid4().hex, "from": sender, "to": to, "subject": subject, "body": body, "at": time.time()}
    _write(_folder(base, to, "inbox") / f"{message['id']}.json", message)
    return message["id"]


def pending(base: Path, agent: str) -> list[tuple[Path, dict[str, Any]]]:
    """The agent's unread messages, oldest first. Unreadable files are skipped."""
    found = []
    for path in sorted(_folder(base, agent, "inbox").glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            found.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            continue
    return found


def mark_done(path: Path) -> None:
    done = path.parent / ".done"
    done.mkdir(exist_ok=True)
    path.replace(done / path.name)


def collect_outboxes(base: Path) -> int:
    """Move every agent's outbox messages into the receivers' inboxes. Returns how many moved."""
    moved = 0
    if not base.is_dir():
        return moved
    for folder in base.iterdir():
        outbox = folder / "outbox"
        if not outbox.is_dir():
            continue
        for path in sorted(outbox.glob("*.json")):
            try:
                message = json.loads(path.read_text(encoding="utf-8"))
                send(base, folder.name, str(message["to"]), str(message.get("subject", "")), str(message.get("body", "")))
            except (OSError, KeyError, ValueError):
                continue
            mark_done(path)
            moved += 1
    return moved
