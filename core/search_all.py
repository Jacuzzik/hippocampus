"""One search box for everything (N.01): notes, messages, tasks, calendar events and agents.

Every word of the query must appear (case does not matter). Notes match on their title and path
first, from the index, then on their text: the text is read from the vault files, at most FILES_MAX
of them and only for a query of 3 or more characters, so a keystroke never reads the whole vault.
Each group returns at most LIMIT rows.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

LIMIT = 8
FILES_MAX = 3000
SNIPPET = 120


def _words(query: str) -> list[str]:
    return [word for word in query.lower().split() if word]


def _has(words: list[str], *parts: object) -> bool:
    text = " ".join(str(part or "") for part in parts).lower()
    return all(word in text for word in words)


def _snippet(text: str, words: list[str]) -> str:
    """The text around the first query word found in it."""
    low = text.lower()
    at = next((i for i in (low.find(word) for word in words) if i >= 0), -1)
    if at < 0:
        return ""
    start = max(0, at - SNIPPET // 3)
    piece = " ".join(text[start : start + SNIPPET].split())
    return ("…" if start else "") + piece + "…"


def notes(
    query: str, titled: list[tuple[str, str]], vault: Path | None, paths: Iterable[str]
) -> list[dict[str, str]]:
    words = _words(query)
    if not words:
        return []
    found = [
        {"path": path, "title": title, "snippet": ""}
        for path, title in titled
        if _has(words, path, title)
    ][:LIMIT]
    if vault is None or len(query.strip()) < 3:
        return found
    seen = {row["path"] for row in found}
    for count, path in enumerate(paths):
        if len(found) >= LIMIT or count >= FILES_MAX:
            break
        if path in seen:
            continue
        try:
            text = (vault / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _has(words, text):
            found.append({"path": path, "title": Path(path).stem, "snippet": _snippet(text, words)})
    return found


def everything(
    query: str,
    note_rows: list[dict[str, str]],
    messages: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    agents: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    words = _words(query)
    if not words:
        return {"notes": [], "messages": [], "tasks": [], "events": [], "agents": []}
    return {
        "notes": note_rows[:LIMIT],
        "messages": [
            {
                "id": m.get("id"),
                "thread": m.get("thread") or m.get("id"),
                "from": m.get("from"),
                "to": m.get("to"),
                "subject": m.get("subject") or "",
                "snippet": _snippet(str(m.get("body") or ""), words),
            }
            for m in messages
            if _has(words, m.get("from"), m.get("to"), m.get("subject"), m.get("body"))
        ][:LIMIT],
        "tasks": [
            {"id": t.get("id"), "title": t.get("title"), "status": t.get("status")}
            for t in tasks
            if _has(words, t.get("id"), t.get("title"), t.get("assignee"))
        ][:LIMIT],
        "events": [
            {
                "id": e.get("id"),
                "date": e.get("date"),
                "time": e.get("time"),
                "title": e.get("title"),
            }
            for e in events
            if _has(words, e.get("title"), e.get("note"), e.get("date"))
        ][:LIMIT],
        "agents": [
            {"id": a.get("id"), "name": a.get("name") or a.get("id")}
            for a in agents
            if _has(words, a.get("id"), a.get("name"), a.get("description"))
        ][:LIMIT],
    }
