"""Finds what is wrong with the links between notes. It only reads; nothing is repaired here."""

from typing import Any

from core.vault.store import Store

LIMIT = 200  # rows of each kind sent to the window; the counts are always complete


def report(store: Store) -> dict[str, Any]:
    """Links that point at no note, and notes that no link reaches or leaves."""
    paths = sorted(store.note_states())
    broken: list[dict[str, str]] = []
    linked: set[str] = set()
    for path in paths:
        for written, target in store.outgoing(path):
            if target is None:
                broken.append({"note": path, "link": written})
            elif target != path:
                linked.update((path, target))
    lonely = [path for path in paths if path not in linked]
    return {
        "notes": len(paths),
        "broken_count": len(broken),
        "lonely_count": len(lonely),
        "broken": broken[:LIMIT],
        "lonely": lonely[:LIMIT],
    }
