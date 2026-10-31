"""The chat window's sessions per agent, on disk, so they show again after a restart.

A session is one Claude Code session (see ai/cli_sessions.py) plus the messages the window showed for it.
The file maps agent id to a list of sessions, oldest first; the last one is the current session.
"""

import json
from pathlib import Path
from typing import Any

from core.settings import ROOT

FILE = ROOT / "storage" / "chat_history.json"
# Messages kept per session; older ones drop off the top.
LIMIT = 300


def _clean(messages: object) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    return [m for m in messages if isinstance(m, dict) and isinstance(m.get("text"), str)][-LIMIT:]


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load(agent: str, path: Path | None = None) -> list[dict[str, Any]]:
    """The agent's sessions, oldest first. Each is {"session": id, "messages": [...]}."""
    path = FILE if path is None else path
    sessions = _read(path).get(agent)
    if not isinstance(sessions, list):
        return []
    return [
        {"session": str(s.get("session", "")), "messages": _clean(s.get("messages"))}
        for s in sessions
        if isinstance(s, dict)
    ]


def save(agent: str, sessions: object, path: Path | None = None) -> None:
    """Replace the agent's sessions with `sessions`, keeping every other agent's."""
    path = FILE if path is None else path
    if not isinstance(sessions, list):
        raise ValueError("sessions must be a list")
    data = _read(path)
    data[agent] = [
        {"session": str(s.get("session", "")), "messages": _clean(s.get("messages"))}
        for s in sessions
        if isinstance(s, dict)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


# How many earlier turns go back to the model with each new message (other providers keep no session).
TURNS = 40


def model_turns(agent: str, path: Path | None = None) -> list[dict[str, Any]]:
    """The agent's current session as model messages: user and assistant text, oldest first."""
    path = FILE if path is None else path
    sessions = load(agent, path)
    if not sessions:
        return []
    turns = [
        {"role": m["role"], "content": m["text"]}
        for m in sessions[-1]["messages"]
        if m.get("role") in ("user", "assistant")
    ]
    return turns[-TURNS:]
