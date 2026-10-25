"""The vault tools: search, read and create notes. Every path must stay inside the vault."""

import difflib
import threading
from pathlib import Path
from typing import Any

from core.vault import Indexer
from tools.registry import Tool

MAX_READ_CHARS = 20_000


def vault_tools(indexer: Indexer, lock: threading.RLock) -> dict[str, Tool]:
    root = indexer.vault

    def note_path(value: object) -> Path:
        if not isinstance(value, str) or not value.endswith(".md"):
            raise ValueError('"path" must be a .md note path inside the vault')
        target = (root / value).resolve()
        if not target.is_relative_to(root):
            raise ValueError("path leaves the vault")
        return target

    def search_notes(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            raise ValueError('"query" is empty')
        with lock:
            hits = indexer.store.search(query)
        if not hits:
            return "no notes match"
        return "\n".join(f"{path}: {title}" for path, title in hits)

    def read_note(args: dict[str, Any]) -> str:
        target = note_path(args.get("path"))
        return target.read_text(encoding="utf-8")[:MAX_READ_CHARS]

    def create_preview(args: dict[str, Any]) -> str:
        target = note_path(args.get("path"))
        content = str(args.get("content", ""))
        rel = target.relative_to(root).as_posix()
        diff = difflib.unified_diff([], content.splitlines(keepends=True), "/dev/null", f"b/{rel}")
        return "".join(diff) or f"create {rel} (empty)"

    def create_note(args: dict[str, Any]) -> str:
        target = note_path(args.get("path"))
        content = str(args.get("content", ""))
        with lock:
            if target.exists():
                raise FileExistsError("the note already exists; this tool never overwrites")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            indexer.apply_changes([target])
        return f"created {target.relative_to(root).as_posix()}"

    path_schema = {
        "type": "string",
        "description": "Note path relative to the vault, ending in .md",
    }
    tools = [
        Tool(
            name="search_notes",
            tier="read",
            description="Find notes whose title or path contains the text.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            run=search_notes,
        ),
        Tool(
            name="read_note",
            tier="read",
            description="Read the text of one note.",
            parameters={
                "type": "object",
                "properties": {"path": path_schema},
                "required": ["path"],
            },
            run=read_note,
        ),
        Tool(
            name="create_note",
            tier="write",
            description="Create a new note. Fails if the note already exists.",
            parameters={
                "type": "object",
                "properties": {"path": path_schema, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            run=create_note,
            preview=create_preview,
        ),
    ]
    return {tool.name: tool for tool in tools}
