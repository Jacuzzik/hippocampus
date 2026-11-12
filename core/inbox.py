"""Messages between agents. Each agent has an inbox and an outbox folder under the app's hive folder.

A message is one JSON file with one schema (see `new_message`). An agent sends by writing a file
into its own outbox; the app checks it and moves it to the receiver's inbox, then types it into the
receiver's terminal and files it under `.done`.

Where a file sits is its state:
  inbox/           queued     waiting to be typed into the receiver's terminal
  inbox/.done/     delivered  typed in (or a "note", which is filed without waking anyone)
  outbox/.done/    sent       the sender's copy of a message that was accepted
  outbox/.failed/  failed     not accepted; the file carries the reason
  outbox/.dropped/ dropped    an acknowledgement-only message, which is never delivered
"""

import gzip
import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# What a message is for. "note" is a record only: it is filed and wakes nobody.
ACTS = ("request", "inform", "note", "propose", "query", "agree", "refuse", "done")
PRIORITIES = ("normal", "urgent")
SUBJECT_MAX = 200
BODY_MAX = 8000
# The app itself and the human are not agents: they have no folder to loop with.
APP = "app"
USER = "user"

# One example, used in the briefing and the start-up inbox, so the text agents read cannot drift from the schema.
EXAMPLE = {
    "to": "hippoherman",
    "act": "done",
    "subject": "DONE: T-12 notes tidied",
    "body": "Moved 4 notes under Projects and fixed 2 broken links. Nothing is waiting on me.",
    "work": "T-12",
}
FORMAT_HELP = (
    'Write one JSON file with the keys "to", "subject" and "body". Optional keys: "act" (one of '
    + ", ".join(ACTS)
    + '; default request), "work" (the task id), "replyTo" (the id of the message you answer) and '
    '"priority" (normal or urgent). A "note" is filed and wakes nobody.'
)


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


def _text(value: object, name: str, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f'"{name}" must be text.')
    return value.strip()[:limit]


def new_message(
    sender: str,
    to: str,
    subject: str,
    body: str,
    *,
    act: str = "request",
    work: str = "",
    reply_to: str = "",
    thread: str = "",
    priority: str = "normal",
) -> dict[str, Any]:
    """One message in the app's schema. Raises ValueError with a plain reason when a field is wrong."""
    to = _text(to, "to", 80)
    if not to:
        raise ValueError('The message has no "to". Name the agent it is for.')
    if act not in ACTS:
        raise ValueError(f'"act" must be one of: {", ".join(ACTS)}.')
    if priority not in PRIORITIES:
        raise ValueError('"priority" must be normal or urgent.')
    subject = _text(subject, "subject", SUBJECT_MAX)
    body = _text(body, "body", BODY_MAX)
    if not subject and not body:
        raise ValueError("The message is empty. Give it a subject or a body.")
    now = time.time()
    message_id = uuid.uuid4().hex
    reply_to = _text(reply_to, "replyTo", 64)
    return {
        "id": message_id,
        "from": sender,
        "to": to,
        "act": act,
        "subject": subject,
        "body": body,
        "work": _text(work, "work", 80),
        "replyTo": reply_to,
        # A reply joins the thread of the message it answers; a new message starts its own.
        "thread": _text(thread, "thread", 64) or reply_to or message_id,
        "priority": priority,
        "at": now,
        "created_at": datetime.fromtimestamp(now, UTC).isoformat(timespec="seconds"),
    }


def send(base: Path, sender: str, to: str, subject: str, body: str, **fields: str) -> str:
    """Put one message in the receiver's inbox and return its id."""
    message = new_message(sender, to, subject, body, **fields)
    _write(_folder(base, message["to"], "inbox") / f"{message['id']}.json", message)
    return str(message["id"])


def pending(base: Path, agent: str) -> list[tuple[Path, dict[str, Any]]]:
    """The agent's queued messages: urgent ones first, then oldest first. Unreadable files are skipped."""
    found = []
    for path in sorted(
        _folder(base, agent, "inbox").glob("*.json"), key=lambda p: p.stat().st_mtime
    ):
        try:
            message = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(message, dict):
            found.append((path, message))
    found.sort(key=lambda item: item[1].get("priority") != "urgent")
    return found


def _file_under(path: Path, folder: str, extra: dict[str, Any] | None = None) -> Path:
    target = path.parent / folder
    target.mkdir(exist_ok=True)
    moved = target / path.name
    if extra:
        try:
            message = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            message = {"raw": path.read_text(encoding="utf-8", errors="replace")[:BODY_MAX]}
        if not isinstance(message, dict):
            message = {"raw": message}
        _write(moved, {**message, **extra})
        path.unlink(missing_ok=True)
    else:
        path.replace(moved)
    return moved


def mark_done(path: Path) -> None:
    _file_under(path, ".done", {"delivered_at": time.time()})


def mark_failed(path: Path, reason: str) -> None:
    """A message that could not be accepted is kept beside the others, with the reason in it."""
    _file_under(path, ".failed", {"failed": reason, "failed_at": time.time()})


_ACK_WORDS = re.compile(
    r"^(ok(ay)?|k|thanks?( you)?|thx|ty|got it|noted|acknowledged?|ack|understood|received|will do|sure|great|perfect|"
    r"sounds good|on it|done|cheers|roger( that)?|copy( that)?|np|no problem|you('| a)re welcome|welcome)$"
)


def is_ack_only(message: dict[str, Any]) -> bool:
    """True for a message that only says thanks or "got it" and carries nothing to act on."""
    if message.get("act") in ("done", "agree", "refuse", "note"):
        return False  # these acts are the answer themselves, however short
    text = f"{message.get('subject') or ''} {message.get('body') or ''}".lower()
    if "?" in text or any(ch.isdigit() for ch in text) or len(text) > 80:
        return False
    parts = [part.strip() for part in re.split(r"[.!,;:\n]+", text) if part.strip()]
    return bool(parts) and all(_ACK_WORDS.match(part) for part in parts)


def collect_outboxes(base: Path, known: set[str] | None = None) -> int:
    """Check every agent's outbox and move good messages into the receivers' inboxes. Returns how many moved.

    The sender is always the folder the file was found in, never the "from" written inside it, so an
    agent cannot send as someone else. `known` is the set of agent ids that exist; with it, a message to
    nobody fails with a reason instead of sitting in a folder no agent reads.
    """
    moved = 0
    if not base.is_dir():
        return moved
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        outbox = folder / "outbox"
        if not outbox.is_dir():
            continue
        sender = folder.name
        for path in sorted(outbox.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("The file must hold one JSON object.")
                message = new_message(
                    sender,
                    raw.get("to", ""),
                    raw.get("subject", ""),
                    raw.get("body", ""),
                    act=raw.get("act") or "request",
                    work=raw.get("work", ""),
                    reply_to=raw.get("replyTo", ""),
                    thread=raw.get("thread", ""),
                    priority=raw.get("priority") or "normal",
                )
                if message["to"] == sender:
                    raise ValueError("A message to yourself is not delivered.")
                if known is not None and message["to"] not in known:
                    raise ValueError(
                        f'No agent has the id "{message["to"]}". Use an id from your start-up inbox.'
                    )
            except OSError:
                continue
            except (json.JSONDecodeError, ValueError) as cause:
                reason = (
                    "The file is not valid JSON."
                    if isinstance(cause, json.JSONDecodeError)
                    else str(cause)
                )
                mark_failed(path, reason)
                _tell(base, sender, "Message not sent", f"{reason} {FORMAT_HELP}")
                continue
            if is_ack_only(message):
                _file_under(
                    path, ".dropped", {"dropped": "acknowledgement only", "dropped_at": time.time()}
                )
                _tell(
                    base,
                    sender,
                    "Message not delivered",
                    f"Your message to {message['to']} only acknowledged, so it was dropped. Send a message only when it carries something to act on.",
                )
                continue
            target = _folder(base, message["to"], "inbox")
            if message["act"] == "note":
                # A note is a record: filed as delivered, typed into no terminal.
                done = target / ".done"
                done.mkdir(exist_ok=True)
                _write(done / f"{message['id']}.json", {**message, "delivered_at": time.time()})
            else:
                _write(target / f"{message['id']}.json", message)
            _file_under(path, ".done", {"id": message["id"], "sent_at": time.time()})
            moved += 1
    return moved


def _tell(base: Path, agent: str, subject: str, body: str) -> None:
    """A short line from the app to an agent about its own message. Never raises: it is a courtesy."""
    try:
        send(base, APP, agent, subject, body, act="inform")
    except (OSError, ValueError):
        pass


class LoopGuard:
    """Stops two agents that keep answering each other: more than `limit` messages between the same
    pair inside `window` seconds holds their messages for `cooldown` seconds."""

    def __init__(self, limit: int = 8, window: float = 60.0, cooldown: float = 300.0) -> None:
        self.limit = limit
        self.window = window
        self.cooldown = cooldown
        self._seen: dict[tuple[str, str], list[float]] = {}
        self._held_until: dict[tuple[str, str], float] = {}

    @staticmethod
    def _pair(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def held(self, a: str, b: str, now: float | None = None) -> bool:
        return (now or time.time()) < self._held_until.get(self._pair(a, b), 0.0)

    def allow(self, sender: str, to: str, now: float | None = None) -> bool:
        """Count one delivery. False means the pair is held and the message must wait."""
        if APP in (sender, to) or USER in (sender, to):
            return True
        now = now or time.time()
        pair = self._pair(sender, to)
        if now < self._held_until.get(pair, 0.0):
            return False
        recent = [at for at in self._seen.get(pair, []) if now - at < self.window]
        recent.append(now)
        self._seen[pair] = recent
        if len(recent) > self.limit:
            self._held_until[pair] = now + self.cooldown
            self._seen[pair] = []
            return False
        return True


_STATES = (
    ("inbox", "queued"),
    ("inbox/.done", "delivered"),
    ("outbox/.failed", "failed"),
    ("outbox/.dropped", "dropped"),
)
_SHOWN = (
    "id",
    "from",
    "to",
    "act",
    "subject",
    "body",
    "work",
    "replyTo",
    "thread",
    "priority",
    "created_at",
    "failed",
)


def all_messages(base: Path) -> list[dict[str, Any]]:
    """Every message the app knows about, with its state, newest first."""
    rows: list[dict[str, Any]] = []
    if not base.is_dir():
        return rows
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        for sub, state in _STATES:
            for file in (folder / sub).glob("*.json"):
                try:
                    message = json.loads(file.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if not isinstance(message, dict):
                    continue
                row = {key: message.get(key) for key in _SHOWN}
                row["id"] = row["id"] or file.stem
                row["thread"] = row["thread"] or row["id"]
                row["act"] = row["act"] or "request"
                # A file found in an outbox was written by that folder's agent, whatever it says inside.
                if sub.startswith("outbox"):
                    row["from"] = folder.name
                row["created_at"] = row["created_at"] or datetime.fromtimestamp(
                    file.stat().st_mtime, UTC
                ).isoformat(timespec="seconds")
                row["state"] = state
                rows.append(row)
    rows.sort(key=lambda row: str(row["created_at"]), reverse=True)
    return rows


def search(base: Path, query: str) -> list[dict[str, Any]]:
    """Messages whose sender, receiver, subject, body or task id holds every word of the query."""
    words = [word for word in query.lower().split() if word]
    if not words:
        return []
    found = []
    for row in all_messages(base):
        text = " ".join(
            str(row.get(key) or "") for key in ("from", "to", "subject", "body", "work", "act")
        ).lower()
        if all(word in text for word in words):
            found.append(row)
    return found


def thread(base: Path, thread_id: str) -> list[dict[str, Any]]:
    """One conversation, oldest first."""
    rows = [
        row for row in all_messages(base) if row["thread"] == thread_id or row["id"] == thread_id
    ]
    rows.sort(key=lambda row: str(row["created_at"]))
    return rows


def export_thread(base: Path, thread_id: str) -> str:
    """One conversation as Markdown, to save or paste elsewhere."""
    rows = thread(base, thread_id)
    if not rows:
        raise ValueError("No message belongs to that thread.")
    lines = [f"# {rows[0].get('subject') or 'Thread'}", ""]
    for row in rows:
        lines += [
            f"## {row['from']} to {row['to']} ({row['act']}, {row['state']})",
            f"_{row['created_at']}_" + (f" · task {row['work']}" if row.get("work") else ""),
            "",
            str(row.get("subject") or ""),
            "",
            str(row.get("body") or ""),
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def archive_old(base: Path, days: int = 30, now: float | None = None) -> int:
    """Move delivered messages older than `days` into one compressed file per month. Returns how many moved."""
    now = now or time.time()
    cutoff = now - days * 86400
    moved = 0
    if not base.is_dir():
        return moved
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        for sub in ("inbox/.done", "outbox/.done", "outbox/.dropped", "outbox/.failed"):
            for file in sorted((folder / sub).glob("*.json")):
                try:
                    stamp = file.stat().st_mtime
                    if stamp >= cutoff:
                        continue
                    text = file.read_text(encoding="utf-8").replace("\n", " ")
                    month = datetime.fromtimestamp(stamp, UTC).strftime("%Y-%m")
                    archive = folder / "archive"
                    archive.mkdir(exist_ok=True)
                    with gzip.open(archive / f"{month}.jsonl.gz", "at", encoding="utf-8") as handle:
                        handle.write(text + "\n")
                    file.unlink()
                    moved += 1
                except OSError:
                    continue
    return moved
