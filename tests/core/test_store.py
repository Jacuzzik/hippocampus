import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from core.vault.parser import parse_note
from core.vault.scanner import NoteFile
from core.vault.store import SCHEMA_VERSION, Store, content_hash, index_path_for


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    vault = tmp_path / "vault"
    vault.mkdir()
    s = Store(tmp_path / "storage" / "index" / "test.sqlite3", vault)
    yield s
    s.close()


def put(store: Store, path: str, text: str) -> None:
    data = text.encode()
    note = NoteFile(path, Path("/unused") / path, 1, len(data))
    store.upsert_note(note, content_hash(data), parse_note(text, path))


def test_index_path_is_per_vault_under_storage(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    a = index_path_for(tmp_path / "a", storage)
    b = index_path_for(tmp_path / "b", storage)
    assert a.parent == storage / "index"
    assert a.suffix == ".sqlite3"
    assert len(a.stem) == 16
    assert a != b
    assert a == index_path_for(tmp_path / "x" / ".." / "a", storage)


def test_new_index_has_schema_and_meta(store: Store) -> None:
    assert store.rebuilt
    meta = dict(store.conn.execute("SELECT key, value FROM meta"))
    assert meta["schema_version"] == str(SCHEMA_VERSION)
    assert store.conn.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    assert store.conn.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_upsert_replaces_links_and_tags(store: Store) -> None:
    put(store, "a.md", "[[B]] [[C]] #one")
    put(store, "a.md", "# New title\n[[C]] #two")
    assert store.note_title("a.md") == "New title"
    assert store.outgoing("a.md") == [("C", None)]
    assert store.tagged("one") == []
    assert store.tagged("#TWO") == ["a.md"]
    assert store.counts()["notes"] == 1


def test_delete_cascades(store: Store) -> None:
    put(store, "a.md", "[[B]] #t")
    assert store.delete_note("a.md")
    assert not store.delete_note("a.md")
    assert store.counts() == {
        "notes": 0,
        "links": 0,
        "dangling_links": 0,
        "tags": 0,
        "distinct_tags": 0,
    }


def test_links_resolve_when_target_appears_and_dangle_when_it_goes(store: Store) -> None:
    put(store, "a.md", "[[Target]]")
    assert store.outgoing("a.md") == [("Target", None)]
    put(store, "folder/target.md", "")
    assert store.outgoing("a.md") == [("Target", "folder/target.md")]
    assert store.backlinks("folder/target.md") == ["a.md"]
    store.delete_note("folder/target.md")
    assert store.outgoing("a.md") == [("Target", None)]
    assert store.counts()["dangling_links"] == 1


def test_duplicate_names_prefer_path_match_then_shortest_path(store: Store) -> None:
    put(store, "projects/deep/Same.md", "")
    put(store, "archive/Same.md", "")
    put(store, "zz/Same.md", "")
    put(store, "a.md", "[[Same]] [[projects/deep/same]] [[Same.md]] [[archive/Same]]")
    assert store.outgoing("a.md") == [
        ("Same", "zz/Same.md"),
        ("projects/deep/same", "projects/deep/Same.md"),
        ("Same.md", "zz/Same.md"),
        ("archive/Same", "archive/Same.md"),
    ]
    put(store, "ab/Same.md", "")  # same length as zz/Same.md: path order breaks the tie
    assert store.outgoing("a.md")[0] == ("Same", "ab/Same.md")


def test_heading_and_alias_links_resolve(store: Store) -> None:
    put(store, "target.md", "")
    put(store, "a.md", "[[target#Part|x]] ![[Target]]")
    assert store.outgoing("a.md") == [("target#Part", "target.md"), ("Target", "target.md")]


def test_update_stat(store: Store) -> None:
    put(store, "a.md", "x")
    store.update_stat("a.md", 99, 7)
    state = store.note_states()["a.md"]
    assert (state.mtime_ns, state.size) == (99, 7)


def test_failed_transaction_rolls_back(store: Store) -> None:
    put(store, "a.md", "x")
    with pytest.raises(sqlite3.IntegrityError), store.transaction() as conn:
        conn.execute("DELETE FROM notes")
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', 'dup')")
    assert store.counts()["notes"] == 1


def test_reopen_keeps_current_index(tmp_path: Path, store: Store) -> None:
    put(store, "a.md", "x")
    store.close()
    again = Store(store.db_path, tmp_path / "vault")
    assert not again.rebuilt
    assert again.counts()["notes"] == 1
    again.close()
