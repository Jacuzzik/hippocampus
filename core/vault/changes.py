"""Tells the app whether the vault changed on disk since it last looked.

The graph is asked for every few seconds. Walking the whole vault each time to find that
nothing changed is wasted work on a large vault, so a background thread watches the folder
and raises a flag; the graph syncs only when the flag is up.
"""

import logging
import threading
from pathlib import Path

from watchfiles import watch

logger = logging.getLogger("hippocampus.core.vault")


class ChangeFlag:
    """Up at the start (so the first look syncs), and after each change on disk.

    If the watch cannot run, the flag stays up for good: every look syncs, as before.
    """

    def __init__(self, vault: Path, *, debounce_ms: int = 400, step_ms: int = 100) -> None:
        self.vault = vault
        self._dirty = threading.Event()
        self._dirty.set()
        self._stop = threading.Event()
        self.broken = False
        self._debounce_ms = debounce_ms
        self._step_ms = step_ms
        self._thread = threading.Thread(target=self._run, name="vault-changes", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            for _changes in watch(
                self.vault,
                stop_event=self._stop,
                watch_filter=None,
                debounce=self._debounce_ms,
                step=self._step_ms,
            ):
                self._dirty.set()
        except Exception as cause:  # a watch that dies must not stop the graph from updating
            if not self._stop.is_set():
                self.broken = True
                logger.warning("Vault watch stopped (%s); syncing on every read instead", cause)

    def mark(self) -> None:
        """Raise the flag by hand, for a change the caller knows about."""
        self._dirty.set()

    def take(self) -> bool:
        """True if the vault may have changed since the last take. Lowers the flag."""
        if self.broken or not self._thread.is_alive():
            return True
        if self._dirty.is_set():
            self._dirty.clear()
            return True
        return False

    def stop(self) -> None:
        self._stop.set()
