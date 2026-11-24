"""Search memory by meaning (7.09).

Each note is turned into a list of numbers (an embedding) by a local embedding model served by
Ollama, on this machine, so no note leaves it. A question is turned the same way and the notes
closest to it are returned, so a search finds a note by what it is about, not only by its words.
The numbers are kept in storage/embeddings.json and a note is read again only after it changes.
"""

import json
import math
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from core import safe_write

OLLAMA = "http://127.0.0.1:11434"
MODEL = "nomic-embed-text"
TEXT_MAX = 2000
NOTES_MAX = 5000

Embed = Callable[[list[str]], list[list[float]]]


class NoModel(ValueError):
    pass


def ollama_embed(texts: list[str], model: str = MODEL) -> list[list[float]]:
    request = urllib.request.Request(  # noqa: S310 (the local Ollama server)
        f"{OLLAMA}/api/embed",
        data=json.dumps({"model": model, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as answer:  # noqa: S310
            data = json.loads(answer.read())
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise NoModel(
                f"The embedding model is not installed. Run `ollama pull {model}`, then build the index again."
            ) from error
        raise NoModel(f"Ollama answered {error.code}.") from error
    except OSError as error:
        raise NoModel(
            f"Ollama is not running here. Install it from ollama.com, run `ollama pull {model}`, then try again."
        ) from error
    return [list(map(float, v)) for v in data.get("embeddings") or []]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    size = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / size if size else 0.0


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"model": MODEL, "notes": {}}
    return (
        data
        if isinstance(data, dict) and isinstance(data.get("notes"), dict)
        else {"model": MODEL, "notes": {}}
    )


def notes_in(vault: Path) -> Iterable[tuple[str, float, Path]]:
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault)
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            yield rel.as_posix(), path.stat().st_mtime, path
        except OSError:
            continue


def build(vault: Path, store: Path, embed: Embed = ollama_embed, batch: int = 16) -> dict[str, Any]:
    """Embed every note that is new or changed; drop notes that are gone."""
    saved = _load(store)
    old = saved["notes"]
    fresh: dict[str, Any] = {}
    todo: list[tuple[str, float, str]] = []
    for rel, mtime, path in list(notes_in(vault))[:NOTES_MAX]:
        kept = old.get(rel)
        if kept and kept.get("mtime") == mtime:
            fresh[rel] = kept
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:TEXT_MAX]
        except OSError:
            continue
        todo.append((rel, mtime, f"{Path(rel).stem}\n{text}"))
    for start in range(0, len(todo), batch):
        part = todo[start : start + batch]
        vectors = embed([t for _, _, t in part])
        for (rel, mtime, _), vector in zip(part, vectors, strict=False):
            fresh[rel] = {"mtime": mtime, "v": [round(x, 5) for x in vector]}
    safe_write.write_text(store, json.dumps({"model": MODEL, "notes": fresh}))
    return {"notes": len(fresh), "read": len(todo)}


def search(
    query: str, store: Path, embed: Embed = ollama_embed, limit: int = 10
) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        raise ValueError("Type what you are looking for.")
    notes = _load(store)["notes"]
    if not notes:
        raise ValueError("The meaning index is empty. Build it first.")
    [vector] = embed([query])
    scored = sorted(((_cosine(vector, row["v"]), rel) for rel, row in notes.items()), reverse=True)
    return [{"path": rel, "score": round(score, 3)} for score, rel in scored[:limit]]


def state(store: Path) -> dict[str, Any]:
    notes = _load(store)["notes"]
    return {"model": MODEL, "notes": len(notes), "built": store.is_file()}
