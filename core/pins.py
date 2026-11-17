"""Notes pinned to an agent (N.23). Their text goes into the agent's briefing at every start, so it is always in
its context. The list of note paths is the "pinned" field of the agent's row in the agents file."""

from collections.abc import Callable
from typing import Any

# Each pinned note is cut at this many characters, so one long note cannot push the briefing past its limit.
CHARS_MAX = 4000
# Past this estimate the window warns that the pinned notes cost a lot on every start.
TOKENS_WARN = 1500


def tokens(text: str) -> int:
    """A rough token count: about four characters a token. Good enough for a warning, not for billing."""
    return (len(text) + 3) // 4


def paths(saved: dict[str, Any]) -> list[str]:
    """The pinned note paths of an agent row, in order, without blanks or repeats."""
    raw = saved.get("pinned")
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip() and item not in seen:
            seen.append(item)
    return seen


def gather(pinned: list[str], read: Callable[[str], str] | None) -> list[dict[str, Any]]:
    """One row per pinned note: its path, its (cut) text, its token estimate, and why it is missing if it is."""
    rows = []
    for path in pinned:
        row: dict[str, Any] = {"path": path, "text": "", "tokens": 0, "cut": False, "missing": ""}
        if read is None:
            row["missing"] = "No vault is open."
        else:
            try:
                text = read(path)
            except (OSError, ValueError) as error:
                row["missing"] = f"Could not read it ({type(error).__name__})."
            else:
                row["cut"] = len(text) > CHARS_MAX
                row["text"] = text[:CHARS_MAX]
                row["tokens"] = tokens(row["text"])
        rows.append(row)
    return rows


def section(rows: list[dict[str, Any]]) -> str:
    """The body of the briefing's "Pinned notes" section, or "" when no pinned note could be read."""
    parts = []
    for row in rows:
        if row["missing"]:
            continue
        cut = "\n(cut here: the note is longer)" if row["cut"] else ""
        parts.append(f"--- {row['path']} ---\n{row['text'].strip()}{cut}")
    if not parts:
        return ""
    return (
        "The user pinned these notes to you. Keep them in mind for the whole session.\n\n"
        + "\n\n".join(parts)
    )


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What the window shows: each note without its text, the total estimate, and whether to warn."""
    total = sum(row["tokens"] for row in rows)
    return {
        "notes": [{k: v for k, v in row.items() if k != "text"} for row in rows],
        "tokens": total,
        "warn": total > TOKENS_WARN,
        "limit": TOKENS_WARN,
    }
