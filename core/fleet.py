"""The live fleet file: fleet.json in the hive folder, one row per agent, for agents and outside tools.

Format 1, stable: {"format": 1, "updated": <epoch seconds>, "agents": [row, ...]} with each row
{"id", "name", "status", "model", "context_percent", "inbox", "started", "last_output", "crashed"}.
"status" is "working", "idle", "stopped" or "crashed"; times are epoch seconds or null. Keys and
commands are never written. The file is rewritten only when a row changes, through a temporary file
and a rename, so a reader never sees half a file.
"""

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from core import safe_write

FORMAT = 1
NAME = "fleet.json"


def row(
    agent: str,
    name: str,
    info: dict[str, Any],
    context: int | None,
    inbox: int,
    started: float | None,
    last_output: float | None,
) -> dict[str, Any]:
    crashed = info.get("crashed")
    if info.get("status") is None:
        status = "crashed" if crashed is not None else "stopped"
    else:
        status = "working" if info["status"] == "Working" else "idle"
    running = status in ("working", "idle")
    return {
        "id": agent,
        "name": name,
        "status": status,
        "model": info.get("model") if isinstance(info.get("model"), str) else None,
        "context_percent": context if running else None,
        "inbox": inbox,
        "started": round(started, 1) if running and started else None,
        "last_output": round(last_output, 1) if running and last_output else None,
        "crashed": crashed if status == "crashed" else None,
    }


def build(
    agents: Iterable[tuple[str, str]],
    info: Callable[[str], dict[str, Any]],
    context: Callable[[str], int | None],
    inbox: Callable[[str], int],
    started: dict[str, float],
    last_output: dict[str, float],
) -> list[dict[str, Any]]:
    rows = []
    for agent, name in agents:
        found = info(agent)
        running = found.get("status") is not None
        rows.append(
            row(
                agent,
                name,
                found,
                context(agent) if running else None,
                inbox(agent),
                started.get(agent),
                last_output.get(agent),
            )
        )
    return rows


def _same(rows: list[dict[str, Any]], path: Path) -> bool:
    """True when the file already holds these rows. Output times move every second while an agent
    prints, so they are compared to the minute; the file then changes at most once a minute per
    working agent, not on every check."""

    def coarse(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {**r, "last_output": int(r["last_output"] // 60) if r.get("last_output") else None}
            for r in items
        ]

    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(held, dict) and coarse(held.get("agents") or []) == coarse(rows)


def write(hive: Path, rows: list[dict[str, Any]], now: float) -> bool:
    """Write the fleet file when it changed. True when it was written."""
    path = hive / NAME
    if _same(rows, path):
        return False
    hive.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(
        path, json.dumps({"format": FORMAT, "updated": round(now, 1), "agents": rows}, indent=2)
    )
    return True
