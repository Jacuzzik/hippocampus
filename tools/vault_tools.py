"""The vault tools: search, read, create, edit and delete notes. Every path must stay inside the vault."""

import difflib
import re
import threading
from pathlib import Path
from typing import Any

import yaml

from core.vault import Indexer
from tools.registry import Tool

# Hub notes linked to MAIN. The chat cannot delete them.
HUB_NOTES = {
    "WELCOME",
    "MAIN",
    "Projects",
    "Summaries",
    "Agent Lists",
    "Contacts",
    "Socials",
    "About User",
    "Test Hub",
}
GROUP_HUBS = ("Projects", "Summaries", "Agent Lists", "Contacts", "Socials", "About User")


def is_hub_stem(stem: str) -> bool:
    """A hub's file name matches without case: the vault may hold Welcome.md for WELCOME."""
    return stem.casefold() in {name.casefold() for name in HUB_NOTES}


def main_guard(root: Path, target: Path) -> None:
    """Refuse to delete MAIN, or any note MAIN links to. Every delete path calls this first."""
    if target.parent == root and target.stem.casefold() == "main":
        raise ValueError("MAIN cannot be deleted. It is the root of the brain.")
    main = root / "MAIN.md"
    if main.is_file() and f"[[{target.stem}]]" in main.read_text(encoding="utf-8"):
        raise ValueError(f"{target.stem} is linked from MAIN, so it cannot be deleted.")


MAX_READ_CHARS = 20_000
# The app's own folder (this repo): exports must never land here.
APP_ROOT = Path(__file__).resolve().parents[1]
STATUS_TAGS = ("important", "done", "pending", "action", "agent")
# Same rule as core/vault/parser.py, which keeps its copy private.
_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?\n)?(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.DOTALL)


def with_status(text: str, status: str | None) -> str:
    """Set status first in frontmatter tags, or drop status tags (graph colours by first tag)."""
    match = _FRONTMATTER.match(text)
    data = yaml.safe_load(match.group(1) or "") if match else {}
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("the frontmatter is not a mapping; fix it by hand")
    value = data.get("tags", data.get("tag"))
    if value is None:
        tags = []
    elif isinstance(value, str):
        tags = [t for t in re.split(r"[,\s]+", value) if t]
    elif isinstance(value, list):
        tags = list(value)
    else:
        raise ValueError("the frontmatter tags are not a list or a string; fix them by hand")
    tags = [t for t in tags if t not in STATUS_TAGS]
    if status:
        tags.insert(0, status)
    data.pop("tag", None)
    if tags:
        data["tags"] = tags
    else:
        data.pop("tags", None)
    body = text[match.end() :] if match else text
    # shortcut: frontmatter is re-dumped, losing comments and key order; upgrade: edit tags in place
    if not data:
        return body
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True) + "---\n" + body


def memory_content(content: str, tag: str = "assistant") -> str:
    """Add created_by: assistant and a tag to the frontmatter. The graph colours a note by its first tag, so an untagged note shows the default colour."""
    # shortcut: a note opening with a --- rule and no frontmatter is misread, upgrade: check fence
    fence_end = content.find("\n---", 4) if content.startswith("---\n") else -1
    has_tags = fence_end > 0 and "\ntags:" in content[:fence_end]
    extra = "" if has_tags else f"tags: [{tag}]\n"
    if content.startswith("---\n"):
        return "---\ncreated_by: assistant\n" + extra + content[4:]
    return f"---\ncreated_by: assistant\n{extra}---\n{content}"


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
        content = memory_content(str(args.get("content", "")))
        rel = target.relative_to(root).as_posix()
        diff = difflib.unified_diff([], content.splitlines(keepends=True), "/dev/null", f"b/{rel}")
        return "".join(diff) or f"create {rel} (empty)"

    def create_note(args: dict[str, Any]) -> str:
        target = note_path(args.get("path"))
        # A note in a folder gets that folder as its tag, so it takes the folder's colour.
        rel_parts = target.relative_to(root).parts
        content = memory_content(
            str(args.get("content", "")), rel_parts[0] if len(rel_parts) > 1 else "assistant"
        )
        with lock:
            if target.exists():
                raise FileExistsError("the note already exists; this tool never overwrites")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            indexer.apply_changes([target])
        return f"created {target.relative_to(root).as_posix()}"

    def edit_preview(args: dict[str, Any]) -> str:
        target = note_path(args.get("path"))
        rel = target.relative_to(root).as_posix()
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        new = str(args.get("content", ""))
        diff = difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{rel}", f"b/{rel}"
        )
        return "".join(diff) or f"edit {rel} (no change)"

    def edit_note(args: dict[str, Any]) -> str:
        target = note_path(args.get("path"))
        content = str(args.get("content", ""))
        with lock:
            if not target.exists():
                raise FileNotFoundError("the note does not exist; use create_note")
            target.write_text(content, encoding="utf-8")
            indexer.apply_changes([target])
        return f"edited {target.relative_to(root).as_posix()}"

    def is_hub(target: Path) -> bool:
        # Hub notes, priority notes, and any note a group hub links to, are kept: only the user deletes them.
        if target.parent == root and is_hub_stem(target.stem):
            return True
        if target.stem.endswith("-PriorityNotes"):
            return True
        link = f"[[{target.stem}]]"
        return any(
            (root / f"{group}.md").is_file()
            and link in (root / f"{group}.md").read_text(encoding="utf-8")
            for group in GROUP_HUBS
        )

    def delete_preview(args: dict[str, Any]) -> str:
        target = note_path(args.get("path"))
        main_guard(root, target)
        if is_hub(target):
            raise ValueError("Hub notes linked to MAIN cannot be deleted.")
        return f"delete {target.relative_to(root).as_posix()}"

    def delete_note(args: dict[str, Any]) -> str:
        target = note_path(args.get("path"))
        main_guard(root, target)
        if is_hub(target):
            raise ValueError("Hub notes linked to MAIN cannot be deleted.")
        with lock:
            if not target.is_file():
                raise FileNotFoundError("the note does not exist")
            target.unlink()
            indexer.apply_changes([target])
        return f"deleted {target.relative_to(root).as_posix()}"

    def list_folders(args: dict[str, Any]) -> str:
        # Visible folders only; hidden folders are never shown.
        folders = sorted(
            p.relative_to(root).as_posix()
            for p in root.rglob("*")
            if p.is_dir() and not any(part.startswith(".") for part in p.relative_to(root).parts)
        )
        return "\n".join(folders) or "no folders"

    def move_plan(args: dict[str, Any]) -> tuple[Path, Path]:
        source = note_path(args.get("path"))
        target = note_path(args.get("to"))
        if not source.is_file():
            raise FileNotFoundError("the note does not exist")
        if any(
            part.startswith(".")
            for part in (*source.relative_to(root).parts, *target.relative_to(root).parts)
        ):
            raise ValueError("hidden folders are never touched")
        if is_hub(source):
            raise ValueError("Hub notes linked to MAIN cannot be moved.")
        if target.exists():
            raise FileExistsError("a note already exists there; this tool never overwrites")
        return source, target

    def move_preview(args: dict[str, Any]) -> str:
        source, target = move_plan(args)
        return (
            f"move {source.relative_to(root).as_posix()} to {target.relative_to(root).as_posix()}"
        )

    def move_note(args: dict[str, Any]) -> str:
        source, target = move_plan(args)
        with lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            indexer.apply_changes([source, target])
        return (
            f"moved {source.relative_to(root).as_posix()} to {target.relative_to(root).as_posix()}"
        )

    def export_plan(args: dict[str, Any]) -> tuple[Path, Path]:
        source = note_path(args.get("path"))
        if any(part.startswith(".") for part in source.relative_to(root).parts):
            raise ValueError("hidden folders are never exported")
        if not source.is_file():
            raise FileNotFoundError("the note does not exist")
        folder = Path(str(args.get("folder", ""))).expanduser()
        if not folder.is_absolute() or not folder.is_dir():
            raise ValueError('"folder" must be an existing absolute folder the user named')
        target = (folder / source.name).resolve()
        # The copy must land outside the vault and outside the app's own folder.
        if (
            target.is_relative_to(root)
            or target.is_relative_to(APP_ROOT)
            or folder.resolve().is_relative_to(APP_ROOT)
        ):
            raise ValueError("the copy must go outside the vault and the app folder")
        if target.exists():
            raise FileExistsError(
                "a file with that name already exists there; this tool never overwrites"
            )
        return source, target

    def export_preview(args: dict[str, Any]) -> str:
        source, target = export_plan(args)
        return f"copy {source.relative_to(root).as_posix()} to {target}"

    def export_note(args: dict[str, Any]) -> str:
        source, target = export_plan(args)
        # Copy only: the note stays in the vault.
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return f"copied {source.relative_to(root).as_posix()} to {target}"

    def status_args(args: dict[str, Any]) -> tuple[Path, str | None]:
        target = note_path(args.get("path"))
        status = args.get("status") or None
        if status is not None and status not in STATUS_TAGS:
            raise ValueError(f'"status" must be one of {", ".join(STATUS_TAGS)}, or empty to clear')
        if not target.is_file():
            raise FileNotFoundError(f"no note at {target.relative_to(root).as_posix()}")
        return target, status

    def set_status_preview(args: dict[str, Any]) -> str:
        target, status = status_args(args)
        old = target.read_text(encoding="utf-8")
        rel = target.relative_to(root).as_posix()
        new = with_status(old, status)
        diff = difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{rel}", f"b/{rel}"
        )
        return "".join(diff) or f"no change to {rel}"

    def set_status(args: dict[str, Any]) -> str:
        target, status = status_args(args)
        rel = target.relative_to(root).as_posix()
        with lock:
            old = target.read_text(encoding="utf-8")
            new = with_status(old, status)
            if new == old:
                return f"no change to {rel}"
            target.write_text(new, encoding="utf-8")
            indexer.apply_changes([target])
        return f"set {rel} status to {status}" if status else f"cleared the status of {rel}"

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
        Tool(
            name="edit_note",
            tier="write",
            description="Replace the whole text of an existing note. Fails if the note does not exist.",
            parameters={
                "type": "object",
                "properties": {"path": path_schema, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            run=edit_note,
            preview=edit_preview,
        ),
        Tool(
            name="delete_note",
            tier="act",
            description="Delete one note. Always asks the user first.",
            parameters={
                "type": "object",
                "properties": {"path": path_schema},
                "required": ["path"],
            },
            run=delete_note,
            preview=delete_preview,
        ),
        Tool(
            name="list_folders",
            tier="read",
            description="List the vault's folders, not hidden ones.",
            parameters={"type": "object", "properties": {}},
            run=list_folders,
        ),
        Tool(
            name="move_note",
            tier="write",
            description="Move one note to a new path in the vault. Fails if the target exists. Hub notes cannot move.",
            parameters={
                "type": "object",
                "properties": {
                    "path": path_schema,
                    "to": {
                        **path_schema,
                        "description": "New note path relative to the vault, ending in .md",
                    },
                },
                "required": ["path", "to"],
            },
            run=move_note,
            preview=move_preview,
        ),
        Tool(
            name="export_note",
            tier="act",
            description="Copy one note to an existing folder outside the app that the user named. The note stays in the vault. Never overwrites.",
            parameters={
                "type": "object",
                "properties": {
                    "path": path_schema,
                    "folder": {
                        "type": "string",
                        "description": "Absolute folder path the user named",
                    },
                },
                "required": ["path", "folder"],
            },
            run=export_note,
            preview=export_preview,
        ),
        Tool(
            name="set_note_status",
            tier="write",
            description=(
                "Set a note's status tag so the graph colours it: important, done, pending, "
                "action or agent. Leave status empty to clear it (the note then takes its folder "
                "colour)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": path_schema,
                    "status": {"type": "string", "enum": [*STATUS_TAGS, ""]},
                },
                "required": ["path"],
            },
            run=set_status,
            preview=set_status_preview,
        ),
    ]
    return {tool.name: tool for tool in tools}
