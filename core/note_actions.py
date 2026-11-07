"""Graph right-click actions on notes: edit, colour and delete, for one note or a hub.

A hub's group is the hub plus the notes it links to. The user picks these in the app
and confirms deletes there. Hub notes are allowed here; the chat tools still refuse them.
"""

import threading
from pathlib import Path

from core.vault import Indexer
from tools.vault_tools import STATUS_TAGS, is_hub_stem, main_guard, with_status

SCOPES = ("note", "hub", "group")


def note_file(root: Path, value: object) -> Path:
    """A note inside the vault that exists and is not in a hidden folder."""
    if not isinstance(value, str) or not value.endswith(".md"):
        raise ValueError('"path" must be a .md note path inside the vault')
    target = (root / value).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("no note at that path")
    if any(part.startswith(".") for part in target.relative_to(root).parts):
        raise ValueError("hidden folders are never touched")
    return target


def is_hub(root: Path, target: Path) -> bool:
    return target.parent == root and is_hub_stem(target.stem)


def _targets(indexer: Indexer, lock: threading.RLock, value: object, scope: str) -> list[Path]:
    """The files a scope covers. A group is its hub plus the notes the hub links to (one level)."""
    if scope not in SCOPES:
        raise ValueError(f'"scope" must be one of {", ".join(SCOPES)}')
    root = indexer.vault
    with lock:
        target = note_file(root, value)
        hub = is_hub(root, target)
        if scope == "note" and hub:
            raise ValueError("hub notes are changed with the hub's own menu items")
        if scope != "note" and not hub:
            raise ValueError("only a hub note has a hub or group action")
        if scope != "group":
            return [target]
        linked = sorted(
            {
                b
                for a, b in indexer.store.graph()["edges"]
                if a == target.relative_to(root).as_posix()
            }
        )
        return [target, *(note_file(root, rel) for rel in linked)]


def read_full(indexer: Indexer, lock: threading.RLock, value: object) -> str:
    """The whole note text. The chat's read_note cuts long notes, so an edit must not use it."""
    with lock:
        return note_file(indexer.vault, value).read_text(encoding="utf-8")


def delete(indexer: Indexer, lock: threading.RLock, value: object, scope: str) -> list[str]:
    with lock:
        # Checked first so MAIN gets its own error, and before any unlink so a refusal deletes nothing.
        main_guard(indexer.vault, note_file(indexer.vault, value))
        files = _targets(indexer, lock, value, scope)
        for target in files:
            main_guard(indexer.vault, target)
        for target in files:
            target.unlink()
        indexer.apply_changes(files)
    return [f.relative_to(indexer.vault).as_posix() for f in files]


def colour(
    indexer: Indexer, lock: threading.RLock, value: object, scope: str, status: object
) -> list[str]:
    """Set the status tag (its colour) on the scope. An empty status clears it to the accent."""
    status = status or None
    if status is not None and status not in STATUS_TAGS:
        raise ValueError(
            f'"status" must be one of {", ".join(STATUS_TAGS)}, or empty for the accent'
        )
    changed: list[Path] = []
    with lock:
        for target in _targets(indexer, lock, value, scope):
            old = target.read_text(encoding="utf-8")
            new = with_status(old, status)
            if new != old:
                target.write_text(new, encoding="utf-8")
                changed.append(target)
        if changed:
            indexer.apply_changes(changed)
    return [f.relative_to(indexer.vault).as_posix() for f in changed]
