"""Notes in the open vault: the graph, reading and saving a note, deleting and colouring."""

from pathlib import Path
from typing import Any

from core import (
    inbox,
    note_actions,
    note_history,
    playbooks,
)
from core.session_shared import DELIVERY_BODY_MAX
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
        self._keep_version(request.get("path"))
        saved = vault_tools(self.indexer, self.lock)["edit_note"].run(
            {"path": request.get("path"), "content": text}
        )
        self.changed("notes")
        return {"saved": saved}

    def _keep_version(self, path: object, force: bool = False) -> None:
        """Keep the note's current text before it is overwritten. A new note has nothing to keep.
        History is best effort: a failure to keep a copy never stops the save."""
        try:
            before = note_actions.read_full(self.indexer, self.lock, path)
        except (OSError, ValueError):
            return
        try:
            note_history.keep(self.storage, str(path), before, force=force)
        except OSError:
            pass

    def note_history(self, request: dict[str, Any]) -> dict[str, Any]:
        self._open_vault()
        path = request.get("path")
        note_actions.read_full(self.indexer, self.lock, path)  # the same path checks as a read
        return {"id": path, "versions": note_history.versions(self.storage, str(path))}

    def note_version(self, request: dict[str, Any]) -> dict[str, Any]:
        self._open_vault()
        path = request.get("path")
        note_actions.read_full(self.indexer, self.lock, path)
        text = note_history.text_of(self.storage, str(path), request.get("version"))
        return {"id": path, "version": request.get("version"), "text": text}

    def note_restore(self, request: dict[str, Any]) -> dict[str, Any]:
        """Put a kept version back. The text it replaces is kept first, so a restore can be undone."""
        self._open_vault()
        path = request.get("path")
        note_actions.read_full(self.indexer, self.lock, path)
        text = note_history.text_of(self.storage, str(path), request.get("version"))
        self._keep_version(path, force=True)
        vault_tools(self.indexer, self.lock)["edit_note"].run({"path": path, "content": text})
        self.changed("notes")
        self.note("setting", text=f"restored an earlier version of {path}")
        return {"id": path, "text": text}

    def card_from_note(self, request: dict[str, Any]) -> dict[str, Any]:
        """Note to card (N.10): the selected text of a note becomes an owner card with a link back."""
        self._open_vault()
        path = request.get("path")
        note_actions.read_full(self.indexer, self.lock, path)  # the same path checks as a read
        text = str(request.get("text") or "").strip()
        if not text:
            raise ValueError("Select some text in the note first.")
        first = next(line for line in text.splitlines() if line.strip()).strip().lstrip("#-* ")
        link = str(path).removesuffix(".md")
        card = self.cards.create(first[:120] or link, f"{text}\n\nFrom [[{link}]]", "owner")
        card = self.cards.set_fields(card["id"], source=str(path))
        self.changed("cards")
        return {"card": card}

    def card_note(self, request: dict[str, Any]) -> dict[str, Any]:
        """Card to note (N.10): the card's own page in the vault's Cards folder, made or updated."""
        self._open_vault()
        card = next((c for c in self.cards.list() if c.get("id") == request.get("id")), None)
        if card is None:
            raise ValueError("No card has that id.")
        safe = "".join(ch for ch in card["title"] if ch.isalnum() or ch in " -_")[:60].strip()
        path = card.get("note") or f"Cards/{safe or 'Card'} {card['id'][:6]}.md"
        text = f"# {card['title']}\n\n{card['body']}\n"
        tools = vault_tools(self.indexer, self.lock)
        try:
            tools["edit_note"].run({"path": path, "content": text})
        except FileNotFoundError:
            tools["create_note"].run({"path": path, "content": text})
        self.cards.set_fields(card["id"], note=path)
        self.changed("notes")
        self.changed("cards")
        return {"note": path}

    def playbook_run(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send a playbook's steps to an agent as one inbox message. The user's click runs it."""
        self._open_vault()
        path, agent = request.get("path"), request.get("agent")
        if not isinstance(path, str) or not playbooks.is_playbook(path):
            raise ValueError(f"Only a note in the {playbooks.FOLDER} folder is a playbook.")
        if agent not in self._agent_ids():
            raise ValueError(f'No agent has the id "{agent}".')
        found = playbooks.parse(path, note_actions.read_full(self.indexer, self.lock, path))
        if not found["steps"]:
            raise ValueError("This playbook has no steps: add a numbered or bulleted list.")
        sent = inbox.send(
            self.hive_path,
            inbox.USER,
            str(agent),
            f"Playbook: {found['title']}",
            playbooks.message(found, str(request.get("note") or ""))[:DELIVERY_BODY_MAX],
            act="request",
            work=f"playbook {found['title']}"[:80],
        )
        self.changed("inbox")
        self.note("handoff", text=f"ran the playbook {path} with {agent}")
        return {"message": sent, "steps": len(found["steps"])}

    def note_delete(self, request: dict[str, Any]) -> dict[str, Any]:
        self._open_vault()
        deleted = note_actions.delete(
            self.indexer, self.lock, request.get("path"), str(request.get("scope"))
        )
        self.changed("notes")
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
        self.changed("notes")
        return {"changed": changed}
