"""Keep a vault's index in step with its files: a full sync, and change batches from the watcher."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from core.vault.parser import parse_note
from core.vault.scanner import NoteFile, iter_notes, read_note, stat_note
from core.vault.store import NoteState, Store, content_hash

logger = logging.getLogger("hippocampus.core.vault")


@dataclass(slots=True)
class IndexStats:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    failed: int = 0

    def __iadd__(self, other: "IndexStats") -> "IndexStats":
        for name in self.__slots__:
            setattr(self, name, getattr(self, name) + getattr(other, name))
        return self


class Indexer:
    def __init__(self, vault: Path, store: Store) -> None:
        self.vault = vault.resolve()
        self.store = store

    def full_sync(self) -> IndexStats:
        """Index new and changed notes and drop notes that are gone.

        A note whose mtime and size match the index is skipped without being read.
        """
        stats = IndexStats()
        known = self.store.note_states()
        seen: set[str] = set()
        for note in iter_notes(self.vault):
            seen.add(note.path)
            stats += self._index(note, known.get(note.path))
        for path in known.keys() - seen:
            self.store.delete_note(path)
            stats.removed += 1
        logger.info("Synced %s: %s", self.vault, stats)
        return stats

    def apply_changes(self, changed: Iterable[Path]) -> IndexStats:
        """Re-index the given absolute paths, which may be files or folders, existing or not."""
        if self.store.reopen_if_deleted():
            return self.full_sync()
        stats = IndexStats()
        known = self.store.note_states()
        for abs_path in sorted(set(changed)):
            try:
                rel = PurePosixPath(abs_path.relative_to(self.vault).as_posix())
            except ValueError:
                logger.warning("Ignoring change outside the vault: %s", abs_path)
                continue
            if abs_path.is_dir() and not abs_path.is_symlink():
                stats += self._sync_folder(abs_path, known)
                continue
            note = stat_note(self.vault, abs_path)
            if note is not None:
                stats += self._index(note, known.get(note.path))
            elif rel.as_posix() in known:
                self.store.delete_note(rel.as_posix())
                stats.removed += 1
            elif not abs_path.exists() and self._has_notes_under(rel, known):
                # A folder was deleted or moved out: drop everything under it.
                stats.removed += self.store.delete_under(rel.as_posix())
        level = logging.INFO if stats != IndexStats() else logging.DEBUG
        logger.log(level, "Applied %s", stats)
        return stats

    @staticmethod
    def _has_notes_under(rel: PurePosixPath, known: dict[str, NoteState]) -> bool:
        prefix = rel.as_posix() + "/"
        return any(path.startswith(prefix) for path in known)

    def _sync_folder(self, folder: Path, known: dict[str, NoteState]) -> IndexStats:
        """Index a folder that was created or moved into the vault."""
        stats = IndexStats()
        for found in iter_notes(folder):
            note = stat_note(self.vault, found.abs_path)  # path relative to the vault, not folder
            if note is not None:
                stats += self._index(note, known.get(note.path))
        return stats

    def _index(self, note: NoteFile, state: NoteState | None) -> IndexStats:
        stats = IndexStats()
        if state is not None and (state.mtime_ns, state.size) == (note.mtime_ns, note.size):
            stats.unchanged += 1
            return stats
        result = read_note(note)
        if result is None:
            if state is not None:
                self.store.delete_note(note.path)
                stats.removed += 1
            return stats
        data, text = result
        digest = content_hash(data)
        try:
            if state is not None and state.content_hash == digest:
                self.store.update_stat(note.path, note.mtime_ns, note.size)
                stats.unchanged += 1
            else:
                self.store.upsert_note(note, digest, parse_note(text, note.path))
                if state is None:
                    stats.added += 1
                else:
                    stats.updated += 1
        except Exception:
            logger.exception("Failed to index %s", note.path)
            stats.failed += 1
        return stats
