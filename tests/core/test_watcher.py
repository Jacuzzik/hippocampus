import asyncio
import os
import time
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from core.vault import Indexer, open_index
from core.vault.watcher import VaultWatcher

pytestmark = pytest.mark.anyio
UPDATE_BUDGET_S = 3.0


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def indexer(sample_vault: tuple[Path, dict[str, Any]], storage: Path) -> Iterator[Indexer]:
    vault, _ = sample_vault
    idx = open_index(vault, storage)
    yield idx
    idx.store.close()


@asynccontextmanager
async def watching(indexer: Indexer) -> AsyncIterator[VaultWatcher]:
    stop = asyncio.Event()
    watcher = VaultWatcher(indexer, tick_ms=200)
    task = asyncio.create_task(watcher.run(stop))
    try:
        await asyncio.wait_for(watcher.ready.wait(), timeout=10)
        yield watcher
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=5)


async def eventually(check: Callable[[], bool], timeout: float = UPDATE_BUDGET_S) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError(f"index did not update within {timeout}s")
        await asyncio.sleep(0.05)


async def test_initial_sync_runs_when_watching_starts(
    sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    _, manifest = sample_vault
    async with watching(indexer):
        assert indexer.store.counts() == manifest["totals"]


async def test_live_edit(sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer) -> None:
    vault, _ = sample_vault
    async with watching(indexer):
        (vault / "projects/Index.md").write_text("# Edited live\n#live", encoding="utf-8")
        await eventually(lambda: indexer.store.note_title("projects/Index.md") == "Edited live")
        assert indexer.store.tagged("live") == ["projects/Index.md"]


async def test_creating_a_note_fixes_dangling_links(
    sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    vault, manifest = sample_vault
    sources = [p for p, n in manifest["notes"].items() if ["Missing Topic 0", None] in n["links"]]
    async with watching(indexer):
        (vault / "resources/Missing Topic 0.md").write_text("here now", encoding="utf-8")
        await eventually(
            lambda: indexer.store.backlinks("resources/Missing Topic 0.md") == sorted(sources)
        )


async def test_delete(sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer) -> None:
    vault, _ = sample_vault
    async with watching(indexer):
        (vault / "archive/Index.md").unlink()
        await eventually(lambda: indexer.store.note_title("archive/Index.md") is None)
        # [[Index]] links now resolve to the remaining note with that name.
        await eventually(lambda: bool(indexer.store.backlinks("projects/Index.md")))


async def test_rename(sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer) -> None:
    vault, _ = sample_vault
    async with watching(indexer):
        os.rename(vault / "archive/Index.md", vault / "archive/Contents.md")
        await eventually(lambda: indexer.store.note_title("archive/Contents.md") == "Index")
        assert indexer.store.note_title("archive/Index.md") is None


async def test_atomic_save(sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer) -> None:
    vault, _ = sample_vault
    target = vault / "projects/Index.md"
    async with watching(indexer):
        tmp = vault / "projects/.Index.md.tmp"
        tmp.write_text("# Saved atomically", encoding="utf-8")
        os.replace(tmp, target)
        await eventually(
            lambda: indexer.store.note_title("projects/Index.md") == "Saved atomically"
        )
        assert indexer.store.counts()["notes"] == 200


async def test_folder_created_with_notes(
    sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    vault, _ = sample_vault
    async with watching(indexer):
        folder = vault / "new/inner"
        folder.mkdir(parents=True)
        for i in range(5):
            (folder / f"n{i}.md").write_text(f"[[n{(i + 1) % 5}]]", encoding="utf-8")
        await eventually(lambda: indexer.store.counts()["notes"] == 205)
        assert indexer.store.backlinks("new/inner/n0.md") == ["new/inner/n4.md"]


async def test_burst_of_edits(sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer) -> None:
    vault, manifest = sample_vault
    paths = list(manifest["notes"])[:50]
    async with watching(indexer):
        for path in paths:
            (vault / path).write_text("# burst\n#burst", encoding="utf-8")
        await eventually(lambda: len(indexer.store.tagged("burst")) == 50)


async def test_index_deleted_while_watching_is_rebuilt(
    sample_vault: tuple[Path, dict[str, Any]], indexer: Indexer
) -> None:
    _, manifest = sample_vault
    async with watching(indexer):
        db = indexer.store.db_path
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db}{suffix}").unlink(missing_ok=True)
        await eventually(lambda: db.exists() and indexer.store.counts() == manifest["totals"])


async def test_failed_batch_is_logged_and_watching_continues(
    sample_vault: tuple[Path, dict[str, Any]],
    indexer: Indexer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    vault, _ = sample_vault
    real = indexer.apply_changes
    failed = False

    def flaky(paths: set[Path]) -> object:
        nonlocal failed
        if paths and not failed:
            failed = True
            raise RuntimeError("disk on fire")
        return real(paths)

    async with watching(indexer):
        monkeypatch.setattr(indexer, "apply_changes", flaky)
        (vault / "first.md").write_text("one", encoding="utf-8")
        await eventually(lambda: failed)
        await asyncio.sleep(0.3)
        (vault / "second.md").write_text("two", encoding="utf-8")
        await eventually(lambda: indexer.store.note_title("second.md") == "second")
    assert "Index update failed" in caplog.text


async def test_stop_is_prompt(indexer: Indexer) -> None:
    stop = asyncio.Event()
    watcher = VaultWatcher(indexer, tick_ms=200)
    task = asyncio.create_task(watcher.run(stop))
    await asyncio.wait_for(watcher.ready.wait(), timeout=10)
    started = time.monotonic()
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert time.monotonic() - started < 1.0
