"""Files the app writes for the user to take away: a picture of the graph, a zip of the notes.

Everything lands in `<storage>/exports/`, never in the vault, so an export cannot change a note.
"""

import re
import zipfile
from datetime import datetime
from pathlib import Path

from core import safe_write

# A graph of a few thousand notes is well under this; a larger text is a mistake, not a picture.
MAX_TEXT = 5_000_000
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,40}\.(svg|md|txt)")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def save_text(storage: Path, name: object, text: object) -> Path:
    """Write one text file into the exports folder and return where it is."""
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError(
            "the file name must be lower-case letters, digits or dashes and end in .svg, .md or .txt"
        )
    if not isinstance(text, str) or not text:
        raise ValueError("there is nothing to save")
    if len(text) > MAX_TEXT:
        raise ValueError("the file is too large to save")
    path = storage / "exports" / f"{_stamp()}-{name}"
    safe_write.write_text(path, text)
    return path


def zip_notes(storage: Path, vault: Path) -> tuple[Path, int]:
    """Copy every note (.md) of the vault into one zip in the exports folder. The vault is only read."""
    notes = sorted(
        path
        for path in vault.rglob("*.md")
        if path.is_file()
        and not any(part.startswith(".") for part in path.relative_to(vault).parts)
    )
    if not notes:
        raise ValueError("this vault has no notes to export")
    target = storage / "exports" / f"{_stamp()}-notes.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as out:
        for path in notes:
            out.write(path, path.relative_to(vault).as_posix())
    temp.replace(target)
    return target, len(notes)
