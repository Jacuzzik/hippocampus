"""One Claude Code session per agent, kept on disk so it survives an app restart.

Each agent gets its session ID the first time it talks. Later calls resume that session.
A new session is made only when the user switches it, by removing the agent's entry.
"""

import json
import uuid
from pathlib import Path
from typing import Any

from core.settings import ROOT

FILE = ROOT / "storage" / "claude_sessions.json"


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(agent: str, path: Path | None = None) -> dict[str, Any]:
    """The agent's entry: {"id": uuid, "started": bool}. Created with a new ID when missing."""
    path = FILE if path is None else path
    data = _read(path)
    entry = data.get(agent)
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        entry = {"id": str(uuid.uuid4()), "started": False}
        data[agent] = entry
        _write(path, data)
    return entry


def mark_started(agent: str, path: Path | None = None) -> None:
    """Call after the session's first reply, so later calls resume it instead of creating it."""
    path = FILE if path is None else path
    data = _read(path)
    if agent in data:
        data[agent]["started"] = True
        _write(path, data)


def switch(agent: str, path: Path | None = None) -> None:
    """Drop the agent's session: the next call starts a new one."""
    path = FILE if path is None else path
    data = _read(path)
    data.pop(agent, None)
    _write(path, data)


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)
