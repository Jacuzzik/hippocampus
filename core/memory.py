"""Assistant memory notes: trimming long ones, and finding them by text or by meaning.

A memory note is a note whose frontmatter says `created_by: assistant`.
Meaning search needs an embedder (a model that turns text into vectors). None is installed,
so it reports "Not set up" until one is given; text search always works.
"""

import math
from pathlib import Path
from typing import Protocol

from core import safe_write

MEMORY_LINE = "created_by: assistant"
ARCHIVE_SUFFIX = "-archive"
NOT_SET_UP = (
    "No embedding model is installed, so search by meaning is not set up. Text search still works."
)


class NotSetUp(Exception):
    """A feature needs a model or service that this install does not have."""


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def is_memory(text: str) -> bool:
    if not text.startswith("---\n"):
        return False
    head = text[4:].split("\n---", 1)[0]
    return MEMORY_LINE in head.splitlines()


def _is_section(line: str) -> bool:
    return line.startswith("## ")


def _is_rules(section: str) -> bool:
    """A section whose heading names rules. It is never moved to the archive."""
    return "rules" in section.split("\n", 1)[0].lower()


def condense(text: str) -> str:
    """The condense step (7.08): drop a list line that says what an earlier one already said (case and spacing
    ignored), and squeeze runs of blank lines to one. The frontmatter and plain text are left alone."""
    lines = text.splitlines(keepends=True)
    start = 0
    if text.startswith("---\n"):
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        start = 0 if end is None else end + 1
    out = lines[:start]
    seen: set[str] = set()
    blank = False
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            if blank:
                continue
            blank = True
            out.append(line)
            continue
        blank = False
        if stripped.startswith(("- ", "* ")):
            key = " ".join(stripped[2:].lower().split())
            if key and key in seen:
                continue
            seen.add(key)
        out.append(line)
    return "".join(out)


def trim_text(text: str, limit: int, stem: str) -> tuple[str, str]:
    """Split a long memory note: (text to keep, sections to archive). Nothing moves under the limit.

    The title, frontmatter and any text before the first "## " stay, and so do the newest section and every
    section whose heading names rules.
    """
    if len(text.encode("utf-8")) <= limit:
        return text, ""
    lines = text.splitlines(keepends=True)
    first = next((i for i, line in enumerate(lines) if _is_section(line)), None)
    if first is None:
        return text, ""
    head = "".join(lines[:first])
    note = f"> Older notes moved to [[{stem}{ARCHIVE_SUFFIX}]].\n"
    if note not in head:
        head = head.rstrip("\n") + "\n\n" + note + "\n" if head.strip() else note + "\n"
    sections: list[str] = []
    for line in lines[first:]:
        if _is_section(line) or not sections:
            sections.append(line)
        else:
            sections[-1] += line
    moved: list[str] = []
    while len(head.encode()) + sum(len(s.encode()) for s in sections) > limit:
        movable = [i for i, s in enumerate(sections) if not _is_rules(s)]
        if len(movable) < 2:
            break
        moved.append(sections.pop(movable[0]))
    if not moved:
        return text, ""
    return head + "".join(sections), "".join(moved)


def trim_memory_file(vault: Path, path: Path, limit: int) -> Path | None:
    """Trim one memory note on disk. Returns the archive written, or None when nothing moved."""
    if path.name.endswith(f"{ARCHIVE_SUFFIX}.md") or not path.is_file():
        return None  # archives are never trimmed, so they cannot grow archives of their own
    text = path.read_text(encoding="utf-8")
    if not is_memory(text) or len(text.encode("utf-8")) <= limit:
        return None
    kept, moved = trim_text(condense(text), limit, path.stem)
    if not moved:
        if kept != text:  # condensing alone brought it under the cap, or was all it could do
            safe_write.write_text(path, kept)
        return None
    archive = path.with_name(f"{path.stem}{ARCHIVE_SUFFIX}.md")
    if archive.is_file():
        archive.write_text(archive.read_text(encoding="utf-8") + moved, encoding="utf-8")
    else:
        head = f"---\n{MEMORY_LINE}\n---\n# {path.stem} archive\n\n"
        archive.write_text(head + moved, encoding="utf-8")
    safe_write.write_text(path, kept)
    return archive


def search_text(notes: dict[str, str], query: str) -> list[str]:
    """Memory note paths whose text or path contains the query, ignoring case."""
    needle = query.strip().lower()
    if not needle:
        raise ValueError('"query" is empty')
    return sorted(p for p, text in notes.items() if needle in text.lower() or needle in p.lower())


def search_meaning(
    notes: dict[str, str], query: str, embedder: Embedder | None, limit: int = 10
) -> list[tuple[str, float]]:
    if embedder is None:
        raise NotSetUp(NOT_SET_UP)
    if not query.strip():
        raise ValueError('"query" is empty')
    paths = sorted(notes)
    vectors = embedder.embed([query] + [notes[p] for p in paths])
    query_vec, note_vecs = vectors[0], vectors[1:]
    scored = [(p, _cosine(query_vec, v)) for p, v in zip(paths, note_vecs, strict=True)]
    return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def status(embedder: Embedder | None) -> dict[str, object]:
    if embedder is None:
        return {"ready": False, "reason": NOT_SET_UP}
    return {"ready": True, "reason": ""}
