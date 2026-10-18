"""Watch a vault and keep its index current while the app runs."""

import asyncio
import functools
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

from watchfiles import awatch

from core.vault.indexer import Indexer, IndexStats

logger = logging.getLogger("hippocampus.core.vault")


class StopEvent(Protocol):
    def is_set(self) -> bool: ...


class VaultWatcher:
    """Runs a full sync once watching has started, then applies each batch of changes.

    Starting the watch before the sync means edits made during the sync are not
    missed: they arrive as the next batch. All index writes run on one thread.
    The watcher also wakes every `tick_ms`, which is how it notices the index
    file was deleted even when the vault is quiet.
    """

    def __init__(self, indexer: Indexer, *, tick_ms: int = 500, step_ms: int = 50) -> None:
        self.indexer = indexer
        self.tick_ms = tick_ms
        self.step_ms = step_ms
        self.ready = asyncio.Event()
        self.batches = 0

    async def run(self, stop_event: StopEvent | None = None) -> None:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="vault-writer") as writer:
            logger.info("Watching %s", self.indexer.vault)
            async for changes in awatch(
                self.indexer.vault,
                stop_event=stop_event,
                watch_filter=None,
                step=self.step_ms,
                rust_timeout=self.tick_ms,
                yield_on_timeout=True,
            ):
                paths = {Path(p) for _, p in changes}
                if not self.ready.is_set():
                    await self._run(loop, writer, self.indexer.full_sync)
                    self.ready.set()
                await self._run(loop, writer, functools.partial(self.indexer.apply_changes, paths))
                if paths:
                    self.batches += 1
        logger.info("Stopped watching %s", self.indexer.vault)

    @staticmethod
    async def _run(
        loop: asyncio.AbstractEventLoop, writer: ThreadPoolExecutor, job: Callable[[], IndexStats]
    ) -> IndexStats | None:
        try:
            return await loop.run_in_executor(writer, job)
        except Exception:
            # One bad batch must not stop the watcher.
            logger.exception("Index update failed")
            return None
