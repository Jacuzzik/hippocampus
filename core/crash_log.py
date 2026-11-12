"""Error records on disk, so a failure leaves a trace after the window closes.

One JSON object per line in storage/crashes.jsonl: when it happened, where, and the message.
Nothing here is sent anywhere. The file is trimmed, so it cannot grow without limit.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FILE = "crashes.jsonl"
KEEP = 500  # rows kept on disk
TRIM_AT = 600  # the file is cut back to KEEP once it passes this many rows
MESSAGE_LIMIT = 2000
SOURCE_LIMIT = 80

_lock = threading.Lock()


def _text(value: object, limit: int) -> str:
    return (value if isinstance(value, str) else repr(value))[:limit]


def record(storage: Path, source: object, message: object, at: object = None) -> dict[str, str]:
    """Append one row and return it. `at` is the caller's ISO time, or now when missing."""
    row = {
        "at": at if isinstance(at, str) and at else datetime.now(UTC).isoformat(timespec="seconds"),
        "source": _text(source, SOURCE_LIMIT) or "unknown",
        "message": _text(message, MESSAGE_LIMIT),
    }
    path = storage / FILE
    with _lock:
        storage.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > TRIM_AT:
            path.write_text("\n".join(lines[-KEEP:]) + "\n", encoding="utf-8")
    return row


def recent(storage: Path, limit: int = 50) -> list[dict[str, Any]]:
    """The newest rows, newest first. A damaged line is skipped, not fatal."""
    path = storage / FILE
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def clear(storage: Path) -> None:
    with _lock:
        (storage / FILE).unlink(missing_ok=True)
