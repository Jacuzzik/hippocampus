"""Notes in the open vault: the graph, reading and saving a note, deleting and colouring."""

from pathlib import Path
from typing import Any

from core import (
    note_actions,
)
from core.vault import open_index
from core.vault.changes import ChangeFlag
from tools.vault_tools import vault_tools


class NotesPart:
    def open(self, vault: Path) -> dict[str, Any]:
        if not vault.is_dir():
            raise ValueError(f"vault folder not found: {vault}")
        with self.lock:
            self.close()
            self.indexer = open_index(vault, self.storage)
            # Started before the sync, so an edit made during it is not missed.
            self.vault_changes = ChangeFlag(vault)
            stats = self.indexer.full_sync()
            self.trim_memory()
            status = {f"{k}_files": getattr(stats, k) for k in stats.__slots__}
            return {"vault": str(vault.resolve()), **self.indexer.store.counts(), **status}

    def graph(self) -> dict[str, Any]:
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            # Notes changed on disk (by the agents or the user) are picked up here. The vault is walked only
            # when the watch saw a change, not on every poll.
            if self.vault_changes is None or self.vault_changes.take():
                self.indexer.full_sync()
            return self.indexer.store.graph()

    def read(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return a note's text. The path checks are the ones `read_note` uses."""
        path = request.get("path")
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            text = vault_tools(self.indexer, self.lock)["read_note"].run({"path": path})
        return {"id": path, "text": text}

    def _open_vault(self) -> None:
        if self.indexer is None:
            raise ValueError("no vault is open")

    def note_text(self, request: dict[str, Any]) -> dict[str, Any]:
        self._open_vault()
        path = request.get("path")
        return {"id": path, "text": note_actions.read_full(self.indexer, self.lock, path)}

    def note_save(self, request: dict[str, Any]) -> dict[str, Any]:
        self._open_vault()
        text = request.get("text")
        if not isinstance(text, str):
            raise ValueError('"note_save" needs the note "text"')
        saved = vault_tools(self.indexer, self.lock)["edit_note"].run(
            {"path": request.get("path"), "content": text}
        )
        return {"saved": saved}

    def note_delete(self, request: dict[str, Any]) -> dict[str, Any]:
        self._open_vault()
        deleted = note_actions.delete(
            self.indexer, self.lock, request.get("path"), str(request.get("scope"))
        )
        return {"deleted": deleted}

    def note_colour(self, request: dict[str, Any]) -> dict[str, Any]:
        self._open_vault()
        changed = note_actions.colour(
            self.indexer,
            self.lock,
            request.get("path"),
            str(request.get("scope")),
            request.get("status"),
        )
        return {"changed": changed}
