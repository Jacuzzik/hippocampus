"""Webhook triggers the user saves in the app. Their list lives in storage/webhooks.json.

A webhook names one kind of job from core.jobs.KINDS. Running it needs the user's approval in the
app, and it only runs that local job. Nothing listens on a port and nothing is sent out.
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any

from core import jobs


def load(path: Path) -> list[dict[str, Any]]:
    """The saved webhooks, or none when the file does not exist yet."""
    if not path.is_file():
        return []
    hooks = json.loads(path.read_text(encoding="utf-8"))
    _check(hooks)
    return hooks


def save(path: Path, hooks: list[dict[str, Any]]) -> None:
    """Write the whole list. A temporary file is renamed over the old one, so a crash keeps it."""
    _check(hooks)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(hooks, indent=2), encoding="utf-8")
    os.replace(temp, path)


def add(hooks: list[dict[str, Any]], name: str, kind: str) -> list[dict[str, Any]]:
    """A new list with one webhook added. The id is made here, never taken from the app."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError('"save_webhook" needs a non-empty "name"')
    if kind not in jobs.KINDS:
        raise ValueError(f'"kind" must be one of {", ".join(jobs.KINDS)}')
    return [*hooks, {"id": uuid.uuid4().hex, "name": name.strip(), "kind": kind}]


def remove(hooks: list[dict[str, Any]], hook_id: str) -> list[dict[str, Any]]:
    kept = [hook for hook in hooks if hook["id"] != hook_id]
    if len(kept) == len(hooks):
        raise ValueError(f"no webhook with id {hook_id!r}")
    return kept


def find(hooks: list[dict[str, Any]], hook_id: str) -> dict[str, Any]:
    for hook in hooks:
        if hook["id"] == hook_id:
            return hook
    raise ValueError(f"no webhook with id {hook_id!r}")


def _check(hooks: object) -> None:
    if not isinstance(hooks, list) or not all(
        isinstance(h, dict)
        and isinstance(h.get("id"), str)
        and isinstance(h.get("name"), str)
        and h.get("kind") in jobs.KINDS
        for h in hooks
    ):
        raise ValueError(
            '"webhooks" must be a list of objects with "id", "name" and a known "kind"'
        )
