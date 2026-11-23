"""Note history: a copy of a note's text kept before it is overwritten, the last 20 per note.

The window saves a note a moment after each pause in typing, so a copy is made only when the newest
copy is older than GAP seconds: one copy per editing session, not one per keystroke. Copies live in
the app's storage, never in the vault, under a folder named by a hash of the note's path, so a path
can never reach outside that folder. A version is named by its time in milliseconds.
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from core import safe_write

KEEP = 20
GAP = 300  # seconds
VERSION = re.compile(r"^\d{13}$")


def _folder(storage: Path, path: str) -> Path:
    return storage / "note-history" / hashlib.sha256(path.encode("utf-8")).hexdigest()[:32]


def _versions(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        (f for f in folder.glob("*.md") if VERSION.match(f.stem)),
        key=lambda f: f.stem,
        reverse=True,
    )


def keep(
    storage: Path, path: str, text: str, now: float | None = None, force: bool = False
) -> bool:
    """Keep `text` (the note before this save) as a version. False when a recent copy already
    holds this editing session (unless `force`, used before a restore), or the text is the same
    as the newest copy."""
    folder = _folder(storage, path)
    stamp = int((time.time() if now is None else now) * 1000)
    found = _versions(folder)
    if found:
        newest = found[0]
        if not force and stamp - int(newest.stem) < GAP * 1000:
            return False
        if stamp <= int(newest.stem):
            stamp = int(newest.stem) + 1
        if newest.read_text(encoding="utf-8") == text:
            return False
    folder.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(folder / "path.json", json.dumps({"path": path}))
    safe_write.write_text(folder / f"{stamp}.md", text)
    for old in found[KEEP - 1 :]:
        old.unlink(missing_ok=True)
    return True


def versions(storage: Path, path: str) -> list[dict[str, Any]]:
    """The kept versions of a note, newest first: id, time (ms), size in characters and first line."""
    out = []
    for f in _versions(_folder(storage, path)):
        text = f.read_text(encoding="utf-8")
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        out.append({"id": f.stem, "time": int(f.stem), "chars": len(text), "first": first[:120]})
    return out


def text_of(storage: Path, path: str, version: object) -> str:
    if not isinstance(version, str) or not VERSION.match(version):
        raise ValueError("That is not a version of this note.")
    f = _folder(storage, path) / f"{version}.md"
    if not f.is_file():
        raise ValueError("That version is no longer kept.")
    return f.read_text(encoding="utf-8")
