"""Find the notes in a vault and read them safely."""

import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

logger = logging.getLogger("hippocampus.core.vault")

MAX_NOTE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class NoteFile:
    path: str  # vault-relative, forward slashes
    abs_path: Path
    mtime_ns: int
    size: int


def is_ignored(rel: PurePosixPath) -> bool:
    """Hidden files and anything under a hidden folder (.obsidian, .git, .trash)."""
    return any(part.startswith(".") for part in rel.parts)


def is_note_name(name: str) -> bool:
    return name.lower().endswith(".md") and len(name) > 3


def stat_note(root: Path, abs_path: Path) -> NoteFile | None:
    """Return the note at `abs_path`, or None if it is missing or must not be indexed."""
    root = root.resolve()
    try:
        rel = PurePosixPath(abs_path.relative_to(root).as_posix())
    except ValueError:
        logger.warning("Skipping %s: not inside the vault %s", abs_path, root)
        return None
    if is_ignored(rel) or not is_note_name(rel.name):
        return None
    try:
        if abs_path.is_symlink() and not abs_path.resolve().is_relative_to(root):
            logger.warning("Skipping %s: symlink points outside the vault", rel)
            return None
        st = abs_path.stat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("Skipping %s: cannot stat: %s", rel, exc)
        return None
    if not abs_path.is_file():
        return None
    if st.st_size > MAX_NOTE_BYTES:
        logger.warning("Skipping %s: %d bytes is over the 5 MB limit", rel, st.st_size)
        return None
    return NoteFile(rel.as_posix(), abs_path, st.st_mtime_ns, st.st_size)


def iter_notes(root: Path) -> Iterator[NoteFile]:
    """Yield every indexable note under `root`, in sorted path order.

    Symlinked folders are not followed, which also rules out loops.
    """
    root = root.resolve()

    def on_error(exc: OSError) -> None:
        logger.warning("Cannot read folder %s: %s", exc.filename, exc.strerror)

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_error):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if is_note_name(name) and not name.startswith("."):
                note = stat_note(root, Path(dirpath) / name)
                if note is not None:
                    yield note


def read_note(note: NoteFile) -> tuple[bytes, str] | None:
    """Return the raw bytes and decoded text, or None if the file vanished or cannot be read."""
    try:
        data = note.abs_path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("Cannot read %s: %s", note.path, exc)
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        logger.warning("%s is not valid UTF-8 (%s); invalid bytes replaced", note.path, exc)
        text = data.decode("utf-8", errors="replace")
    return data, text
