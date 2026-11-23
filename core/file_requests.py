"""File-based requests (7.35): a watched folder, requests/ in the hive, that turns a JSON file into an
inbox message, for scripts and other tools that cannot call the app.

A request is one file `requests/<name>.json`: {"to": "<agent id>", "subject": "...", "body": "...",
"priority": "normal" | "urgent", "work": "..."}. The delivery loop reads the folder every few seconds.
A good request becomes a message from the user to that agent and its file moves to requests/.done/;
a bad one moves to requests/.failed/ with an "error" saying why. A file is read only once it is a
second old, so a half-written file is not taken.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

FOLDER = "requests"
MAX_BYTES = 20_000
SETTLE_S = 1.0
SUBJECT_MAX = 200
BODY_MAX = 4000


def _move(path: Path, folder: str, extra: dict[str, Any] | None = None) -> None:
    target = path.parent / folder
    target.mkdir(exist_ok=True)
    name = f"{int(time.time() * 1000)}-{path.name}"
    if extra is None:
        path.replace(target / name)
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {"raw": path.read_text(encoding="utf-8", errors="replace")[:MAX_BYTES]}
    if not isinstance(data, dict):
        data = {"raw": data}
    (target / name).write_text(json.dumps({**data, **extra}, indent=2), encoding="utf-8")
    path.unlink(missing_ok=True)


def check(data: object, known: set[str]) -> dict[str, str]:
    if not isinstance(data, dict):
        raise ValueError("A request is one JSON object.")
    to = data.get("to")
    if not isinstance(to, str) or to not in known:
        raise ValueError(f'"to" must be one of: {", ".join(sorted(known))}.')
    subject, body = data.get("subject"), data.get("body")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError('"subject" must be a short line of text.')
    if not isinstance(body, str) or not body.strip():
        raise ValueError('"body" must say what to do.')
    priority = data.get("priority", "normal")
    if priority not in ("normal", "urgent"):
        raise ValueError('"priority" must be "normal" or "urgent".')
    work = data.get("work", "")
    return {
        "to": to,
        "subject": subject.strip()[:SUBJECT_MAX],
        "body": body.strip()[:BODY_MAX],
        "priority": str(priority),
        "work": str(work)[:80] if isinstance(work, str) else "",
    }


def process(
    hive: Path, known: set[str], send: Callable[[dict[str, str]], None], now: float | None = None
) -> tuple[int, int]:
    """Take every settled request file. Returns how many were sent and how many failed."""
    folder = hive / FOLDER
    if not folder.is_dir():
        return 0, 0
    now = time.time() if now is None else now
    sent = failed = 0
    for path in sorted(folder.glob("*.json")):
        try:
            if now - path.stat().st_mtime < SETTLE_S:
                continue
            if path.stat().st_size > MAX_BYTES:
                raise ValueError(f"The file is larger than {MAX_BYTES} bytes.")
            request = check(json.loads(path.read_text(encoding="utf-8")), known)
        except FileNotFoundError:
            continue
        except (ValueError, OSError) as error:
            _move(path, ".failed", {"error": str(error)})
            failed += 1
            continue
        send(request)
        _move(path, ".done")
        sent += 1
    return sent, failed
