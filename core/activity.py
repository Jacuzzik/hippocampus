"""The activity log: handoffs, tool calls, approvals, errors and budget pauses, one JSON line each.

Only names, tiers and outcomes are kept. Note text, previews and keys are never written here.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

KINDS = ("handoff", "tool", "approval", "error", "budget", "setting")
_lock = threading.Lock()


def record(storage: Path, kind: str, **fields: str | int | bool | None) -> None:
    if kind not in KINDS:
        raise ValueError(f"unknown activity kind: {kind}")
    row = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"), "kind": kind, **fields}
    with _lock:
        storage.mkdir(parents=True, exist_ok=True)
        with (storage / "activity.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(row) + "\n")


def clear(storage: Path) -> None:
    """Empty the activity history. The file stays, so the next event is written as usual."""
    path = storage / "activity.jsonl"
    if path.is_file():
        path.write_text("", encoding="utf-8")


def read(
    storage: Path,
    kind: str | None = None,
    limit: int = 200,
    *,
    since: str | None = None,
    until: str | None = None,
    agent: str | None = None,
) -> list[dict[str, Any]]:
    """Newest first. `kind` None means every kind. `since` and `until` are dates (YYYY-MM-DD, both
    inclusive); `agent` keeps rows that name that agent in their `agent` field."""
    path = storage / "activity.jsonl"
    with _lock:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    rows = [json.loads(line) for line in lines if line.strip()]
    if kind is not None:
        rows = [row for row in rows if row.get("kind") == kind]
    if since:
        rows = [row for row in rows if str(row.get("ts", ""))[:10] >= since]
    if until:
        rows = [row for row in rows if str(row.get("ts", ""))[:10] <= until]
    if agent:
        rows = [row for row in rows if row.get("agent") == agent]
    return rows[::-1][:limit]
