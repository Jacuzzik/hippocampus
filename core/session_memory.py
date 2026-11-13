"""Agents' memory notes: the list, the size meter and search."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from core import memory as memory_notes
from core.session_shared import (
    DEFAULT_HIVE_DIR,
)
from core.vault.scanner import iter_notes


class MemoryPart:
    def memory_notes(self) -> dict[str, Any]:
        # Read-only list of each agent's memory.md: size and last update, newest first.
        agents = Path(os.environ.get("MD_HIVE_DIR", DEFAULT_HIVE_DIR)) / "agents"
        rows: list[dict[str, Any]] = []
        for file in agents.glob("*/memory.md"):
            try:
                stat = file.stat()
            except OSError:
                continue
            rows.append(
                {
                    "agent": file.parent.name,
                    "bytes": stat.st_size,
                    "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="minutes"
                    ),
                }
            )
        rows.sort(key=lambda r: r["updated_at"], reverse=True)
        return {"notes": rows, "max_bytes": self.settings.memory_max_bytes}

    def _memory_texts(self) -> dict[str, str]:
        """Every assistant memory note's text, keyed by vault path."""
        if self.indexer is None:
            raise ValueError("no vault is open")
        notes = {}
        for note in iter_notes(self.indexer.vault):
            text = (self.indexer.vault / note.path).read_text(encoding="utf-8", errors="replace")
            if memory_notes.is_memory(text):
                notes[note.path] = text
        return notes

    def memory_search(self, request: dict[str, Any]) -> dict[str, Any]:
        mode = request.get("mode", "text")
        query = request.get("query")
        if not isinstance(query, str):
            raise ValueError('"query" must be text')
        with self.lock:
            notes = self._memory_texts()
        if mode == "text":
            return {"mode": mode, "hits": memory_notes.search_text(notes, query)}
        if mode != "meaning":
            raise ValueError('"mode" is "text" or "meaning"')
        ranked = memory_notes.search_meaning(notes, query, self.embedder)
        return {"mode": mode, "hits": [{"path": p, "score": round(s, 3)} for p, s in ranked]}

    def memory_status(self) -> dict[str, Any]:
        return {**memory_notes.status(self.embedder), "max_bytes": self.settings.memory_max_bytes}
