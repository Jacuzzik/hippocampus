"""Agents the user added in the app. Their list lives in storage/agents.json.

Each agent is one object with a string "id" and "name" plus the form's fields. The sidecar
stores them as given, so the app owns the rest of the shape.
"""

import json
import os
from pathlib import Path
from typing import Any


def load(path: Path) -> list[dict[str, Any]]:
    """The saved agents, or none when the file does not exist yet."""
    if not path.is_file():
        return []
    agents = json.loads(path.read_text(encoding="utf-8"))
    _check(agents)
    return agents


def save(path: Path, agents: list[dict[str, Any]]) -> None:
    """Write the whole list. A temporary file is renamed over the old one, so a crash keeps it."""
    _check(agents)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(agents, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _check(agents: object) -> None:
    if not isinstance(agents, list) or not all(
        isinstance(a, dict) and isinstance(a.get("id"), str) and isinstance(a.get("name"), str)
        for a in agents
    ):
        raise ValueError('"agents" must be a list of objects with a string "id" and "name"')
