"""The data folder's version. A change to how the folder is laid out gets a number here, and a step that
brings an older folder up to it. Before any step runs, the folder is copied to `backups/`, so nothing is lost."""

import logging
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core import safe_write

logger = logging.getLogger("hippocampus.core")

CURRENT = 1
FILE = "data_version"
# What the backup leaves out: the search index is rebuilt from the notes, and terminal logs are large.
NOT_BACKED_UP = ("index", "terminals")

# Old version -> the step that brings the folder to the next one. Version 0 is a folder from before this file existed.
STEPS: dict[int, Callable[[Path], None]] = {
    0: lambda _storage: None,  # layout unchanged: only the version file is new
}


class NewerData(RuntimeError):
    """The folder was written by a newer app. Opening it with this one could lose data, so it is refused."""


def read_version(storage: Path) -> int | None:
    try:
        return int((storage / FILE).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def backup(storage: Path, old: int, now: datetime | None = None) -> Path:
    """Copies the folder (minus NOT_BACKED_UP) to `<storage>/../backups/storage-v<old>-<time>`."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    base = storage.parent / "backups" / f"storage-v{old}-{stamp}"
    target, n = base, 1
    while target.exists():  # two starts in one second must not share a folder
        n += 1
        target = base.with_name(f"{base.name}-{n}")
    shutil.copytree(storage, target, ignore=shutil.ignore_patterns(*NOT_BACKED_UP))
    return target


def migrate(storage: Path) -> Path | None:
    """Brings the folder to CURRENT. Returns the backup made, or None when nothing had to change."""
    storage.mkdir(parents=True, exist_ok=True)
    version = read_version(storage)
    if version is None:
        # No file: a new, empty folder starts at CURRENT; one with content is version 0.
        if not any(storage.iterdir()):
            safe_write.write_text(storage / FILE, f"{CURRENT}\n")
            return None
        version = 0
    if version > CURRENT:
        raise NewerData(
            f"The data folder {storage} was made by a newer version of the app (data version {version}); "
            f"this one understands up to {CURRENT}. Update the app, or restore a backup."
        )
    if version == CURRENT:
        return None
    saved = backup(storage, version)
    logger.info("Data folder is version %s; backed up to %s before migrating", version, saved)
    while version < CURRENT:
        STEPS[version](storage)
        version += 1
        safe_write.write_text(storage / FILE, f"{version}\n")
    return saved
