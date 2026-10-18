"""Deleting or damaging the index must always be safe: it is rebuilt from the vault."""

import logging
from pathlib import Path

import pytest

from core.vault.parser import parse_note
from core.vault.scanner import NoteFile
from core.vault.store import Store, content_hash


def build(tmp_path: Path) -> tuple[Store, Path]:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    store = Store(tmp_path / "index" / "v.sqlite3", vault)
    data = b"[[x]]"
    store.upsert_note(
        NoteFile("a.md", vault / "a.md", 1, 5), content_hash(data), parse_note("", "a")
    )
    return store, vault


def sidecars(db: Path) -> list[Path]:
    return [Path(f"{db}{s}") for s in ("", "-wal", "-shm")]


@pytest.mark.parametrize("which", [("",), ("", "-wal", "-shm"), ("-wal", "-shm")])
def test_deleted_files_reopen_cleanly(tmp_path: Path, which: tuple[str, ...]) -> None:
    store, vault = build(tmp_path)
    store.close()
    for suffix in which:
        Path(f"{store.db_path}{suffix}").unlink(missing_ok=True)
    again = Store(store.db_path, vault)
    assert again.rebuilt == ("" in which)
    assert again.counts()["notes"] == (0 if "" in which else 1)
    again.close()


def test_missing_storage_folder_is_created(tmp_path: Path) -> None:
    store = Store(tmp_path / "does" / "not" / "exist" / "v.sqlite3", tmp_path)
    assert store.db_path.exists()
    store.close()


def test_corrupt_file_is_logged_deleted_and_rebuilt(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store, vault = build(tmp_path)
    store.close()
    for path in sidecars(store.db_path):
        path.unlink(missing_ok=True)
    store.db_path.write_bytes(b"this is not a database" * 100)
    with caplog.at_level(logging.WARNING, logger="hippocampus.core.vault"):
        again = Store(store.db_path, vault)
    assert again.rebuilt
    assert again.counts()["notes"] == 0
    assert "unreadable" in caplog.text
    again.close()


def test_schema_version_mismatch_rebuilds(tmp_path: Path) -> None:
    store, vault = build(tmp_path)
    store.conn.execute("UPDATE meta SET value = '0' WHERE key = 'schema_version'")
    store.close()
    again = Store(store.db_path, vault)
    assert again.rebuilt
    assert again.counts()["notes"] == 0
    again.close()


def test_index_for_a_different_vault_rebuilds(tmp_path: Path) -> None:
    store, _ = build(tmp_path)
    store.close()
    (tmp_path / "other").mkdir()
    again = Store(store.db_path, tmp_path / "other")
    assert again.rebuilt
    again.close()


def test_unrelated_sqlite_file_rebuilds(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "v.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE something_else (x)")
    conn.close()
    store = Store(db, tmp_path)
    assert store.rebuilt
    assert store.counts()["notes"] == 0
    store.close()


def test_deleted_while_open_is_detected(tmp_path: Path) -> None:
    store, _ = build(tmp_path)
    assert not store.reopen_if_deleted()
    for path in sidecars(store.db_path):
        path.unlink(missing_ok=True)
    assert store.reopen_if_deleted()
    assert store.rebuilt
    assert store.db_path.exists()
    assert store.counts()["notes"] == 0
    store.close()
