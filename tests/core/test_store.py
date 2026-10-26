import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from core.vault.parser import parse_note
from core.vault.scanner import NoteFile
from core.vault.store import (
    _SCHEMA,
    SCHEMA_VERSION,
    Store,
    check_sqlite_version,
    content_hash,
    index_path_for,
)


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


def test_view_has_no_subquery_or_star() -> None:
    # SQLite 3.45 rejects outer references in a subquery's ORDER BY, so the view uses none.
    view = " ".join(_SCHEMA[_SCHEMA.index("CREATE VIEW") :].split()).upper()
    assert "(SELECT" not in view
    assert ".*" not in view


@pytest.mark.parametrize("version", [(3, 34, 1), (3, 24, 0), (2, 99, 99)])
def test_old_sqlite_is_rejected(version: tuple[int, int, int]) -> None:
    with pytest.raises(RuntimeError, match=r"needs SQLite 3\.35\.0 or newer; found"):
        check_sqlite_version(version)


@pytest.mark.parametrize("version", [(3, 35, 0), (3, 45, 1), (4, 0, 0)])
def test_supported_sqlite_is_accepted(version: tuple[int, int, int]) -> None:
    check_sqlite_version(version)


def test_store_refuses_old_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 31, 1))
    with pytest.raises(RuntimeError, match="found 3.31.1"):
        Store(tmp_path / "x.sqlite3", tmp_path)
    assert not (tmp_path / "x.sqlite3").exists()


def test_graph_lists_notes_with_tags_and_unique_resolved_edges(store: Store) -> None:
    put(store, "a.md", "# Alpha\n[[b]] [[b]] [[a]] [[missing]] #one")
    put(store, "b.md", "[[a]] #two #one")
    graph = store.graph()
    assert graph["nodes"] == [
        {"id": "a.md", "title": "Alpha", "tags": ["one"], "memory": False},
        {"id": "b.md", "title": "b", "tags": ["one", "two"], "memory": False},
    ]
    assert graph["edges"] == [["a.md", "b.md"], ["b.md", "a.md"]]


def test_graph_marks_only_assistant_created_notes_as_memory(store: Store) -> None:
    put(store, "mem.md", "---\ncreated_by: assistant\n---\n# Mem\n")
    put(store, "other.md", "---\ncreated_by: human\n---\n# Other\n")
    put(store, "plain.md", "# Plain\n")
    memory = {n["id"]: n["memory"] for n in store.graph()["nodes"]}
    assert memory == {"mem.md": True, "other.md": False, "plain.md": False}
