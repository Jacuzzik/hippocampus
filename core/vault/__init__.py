"""Vault indexing: scan Markdown notes, parse links and tags, keep a SQLite cache."""

from pathlib import Path

from core.vault.indexer import Indexer, IndexStats
from core.vault.store import Store, index_path_for

__all__ = ["IndexStats", "Indexer", "Store", "index_path_for", "open_index"]


def open_index(vault: Path, storage: Path) -> Indexer:
    """Open (or create) the index for `vault` under `storage`. Call `full_sync()` to fill it."""
    return Indexer(vault, Store(index_path_for(vault, storage), vault))
