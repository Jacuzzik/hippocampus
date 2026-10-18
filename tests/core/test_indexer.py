import os
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.vault import Indexer, index_path_for, open_index
from fixtures.make_sample_vault import generate


@pytest.fixture
def indexer(sample_vault: tuple[Path, dict[str, Any]], storage: Path) -> Iterator[Indexer]:
    vault, _ = sample_vault
    idx = open_index(vault, storage)
    idx.full_sync()
    yield idx
    idx.store.close()


def bump(path: Path, text: str) -> None:
    """Write and move the mtime forward, so the change is seen even on coarse clocks."""
    path.write_text(text, encoding="utf-8")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))


def test_index_lives_under_storage_only(
    sample_vault: tuple[Path, dict[str, Any]], storage: Path, indexer: Indexer
) -> None:
    vault, _ = sample_vault
    assert indexer.store.db_path == index_path_for(vault, storage)
    assert indexer.store.db_path.is_relative_to(storage)
    assert not list(vault.rglob("*.sqlite3*"))


def test_full_index_matches_manifest(
    sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    _, manifest = sample_vault
    store = indexer.store
    assert store.counts() == manifest["totals"]
    for path, expected in manifest["notes"].items():
        assert store.note_title(path) == expected["title"], path
        assert store.outgoing(path) == [tuple(link) for link in expected["links"]], path
    for tag in {key for note in manifest["notes"].values() for key, _ in note["tags"]}:
        expected_paths = sorted(
            p for p, n in manifest["notes"].items() if any(k == tag for k, _ in n["tags"])
        )
        assert store.tagged(tag) == expected_paths
    for orphan in manifest["orphans"]:
        assert store.backlinks(orphan) == []
        assert store.outgoing(orphan) == []
    assert store.tagged("not-a-tag") == []
    assert store.backlinks("projects/Index.md") == []
    assert store.backlinks("archive/Index.md")


def test_second_sync_reads_nothing(indexer: Indexer, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: object) -> None:
        raise AssertionError("unchanged notes must not be read")

    monkeypatch.setattr("core.vault.indexer.read_note", fail)
    stats = indexer.full_sync()
    assert (stats.added, stats.updated, stats.removed, stats.unchanged) == (0, 0, 0, 200)


def test_touch_without_change_updates_stat_only(
    sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    vault, _ = sample_vault
    path = vault / "projects/Index.md"
    bump(path, path.read_text(encoding="utf-8"))
    stats = indexer.full_sync()
    assert (stats.updated, stats.unchanged) == (0, 200)
    assert indexer.store.note_states()["projects/Index.md"].mtime_ns == path.stat().st_mtime_ns


def test_offline_edit_add_and_delete(
    sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    vault, manifest = sample_vault
    store = indexer.store
    bump(vault / "projects/Index.md", "# Renamed\n[[Missing Topic 0]] #fresh")
    (vault / "Missing Topic 0.md").write_text("now exists", encoding="utf-8")
    victim = manifest["orphans"][0]
    (vault / victim).unlink()

    stats = indexer.full_sync()
    assert (stats.added, stats.updated, stats.removed) == (1, 1, 1)
    assert store.note_title("projects/Index.md") == "Renamed"
    assert store.tagged("fresh") == ["projects/Index.md"]
    assert store.note_title(victim) is None
    assert store.counts()["dangling_links"] == manifest["totals"]["dangling_links"] - 2
    assert "projects/Index.md" in store.backlinks("Missing Topic 0.md")


def test_apply_changes_for_files(
    sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    vault, _ = sample_vault
    store = indexer.store
    new = vault / "areas/New.md"
    new.write_text("[[Index]] #new", encoding="utf-8")
    edited = vault / "projects/Index.md"
    bump(edited, "edited")
    removed = vault / "archive/Index.md"
    removed.unlink()

    stats = indexer.apply_changes([new, edited, removed, vault / ".obsidian/app.json"])
    assert (stats.added, stats.updated, stats.removed) == (1, 1, 1)
    assert store.outgoing("areas/New.md") == [("Index", "projects/Index.md")]
    assert store.note_title("projects/Index.md") == "Index"
    assert store.note_title("archive/Index.md") is None


def test_apply_changes_ignores_paths_outside_vault(
    tmp_path: Path, indexer: Indexer, caplog: pytest.LogCaptureFixture
) -> None:
    outside = tmp_path / "elsewhere.md"
    outside.write_text("x", encoding="utf-8")
    assert indexer.apply_changes([outside]).added == 0
    assert "outside the vault" in caplog.text


def test_folder_moved_out_and_back_in(
    tmp_path: Path, sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    vault, manifest = sample_vault
    in_folder = sorted(p for p in manifest["notes"] if p.startswith("areas/health/"))
    assert in_folder
    parked = tmp_path / "parked"
    shutil.move(vault / "areas/health", parked)

    stats = indexer.apply_changes([vault / "areas/health"])
    assert stats.removed == len(in_folder)
    assert all(indexer.store.note_title(p) is None for p in in_folder)
    assert indexer.store.note_title("areas/" + Path(in_folder[0]).name) is None

    shutil.move(parked, vault / "areas/health")
    stats = indexer.apply_changes([vault / "areas/health"])
    assert stats.added == len(in_folder)
    assert indexer.store.counts() == manifest["totals"]


def test_parse_failure_is_logged_and_others_continue(
    sample_vault: tuple[Path, dict[str, Any]],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    vault, _ = sample_vault
    from core.vault import indexer as indexer_module

    real = indexer_module.parse_note

    def flaky(text: str, path: str) -> object:
        if path == "projects/Index.md":
            raise ValueError("boom")
        return real(text, path)

    monkeypatch.setattr(indexer_module, "parse_note", flaky)
    idx = open_index(vault, storage)
    stats = idx.full_sync()
    assert (stats.added, stats.failed) == (199, 1)
    assert "projects/Index.md" in caplog.text
    idx.store.close()


@pytest.mark.slow
def test_2000_notes_index_quickly(tmp_path: Path) -> None:
    vault = tmp_path / "big"
    manifest = generate(vault, count=2000)
    idx = open_index(vault, tmp_path / "storage")
    start = time.perf_counter()
    idx.full_sync()
    elapsed = time.perf_counter() - start
    assert idx.store.counts() == manifest["totals"]
    idx.store.close()
    assert elapsed < 10, f"indexing 2,000 notes took {elapsed:.1f}s"
