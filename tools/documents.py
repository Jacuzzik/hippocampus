"""Documents in the vault that are not notes (7.12): plain text, CSV and PDF files, searched and read on demand.

Nothing is indexed ahead of time, so an idle app spends nothing on them. A PDF's text comes from the `pdftotext`
program (poppler) with a time limit, and is kept in memory per file and modification time.
"""

import os
import shutil
import subprocess
import threading
from pathlib import Path

KINDS = (".txt", ".csv", ".pdf")
READ_MAX = 20_000
HITS_MAX = 20
FILES_MAX = 2000
PDF_PAGES = 50
PDF_TIMEOUT_S = 10
SNIPPET = 80
_cache: dict[tuple[str, float], str] = {}
_lock = threading.Lock()


def files(root: Path) -> list[Path]:
    """The documents under the vault, skipping hidden folders and files, in path order, at most FILES_MAX."""
    found: list[Path] = []
    for dirpath, dirnames, names in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(names):
            if not name.startswith(".") and Path(name).suffix.lower() in KINDS:
                found.append(Path(dirpath) / name)
                if len(found) >= FILES_MAX:
                    return found
    return found


def text_of(path: Path) -> str:
    """The text of one document. A PDF needs `pdftotext`; without it, ValueError says so."""
    if path.suffix.lower() != ".pdf":
        return path.read_text(encoding="utf-8", errors="replace")
    key = (str(path), path.stat().st_mtime)
    with _lock:
        if key in _cache:
            return _cache[key]
    program = shutil.which("pdftotext")
    if program is None:
        raise ValueError("PDFs cannot be read: the pdftotext program (poppler) is not installed")
    try:
        done = subprocess.run(
            [program, "-l", str(PDF_PAGES), "-enc", "UTF-8", str(path), "-"],
            capture_output=True,
            timeout=PDF_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"{path.name} took too long to read") from error
    if done.returncode != 0:
        raise ValueError(f"{path.name} could not be read as a PDF")
    text = done.stdout.decode("utf-8", errors="replace")
    with _lock:
        _cache[key] = text
    return text


def inside(root: Path, value: object) -> Path:
    """A document path inside the vault, or ValueError."""
    if not isinstance(value, str) or Path(value).suffix.lower() not in KINDS:
        raise ValueError(f'"path" must be a {", ".join(KINDS)} file inside the vault')
    target = (root / value).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("no document at that path")
    if any(part.startswith(".") for part in target.relative_to(root).parts):
        raise ValueError("hidden folders are never read")
    return target


def search(root: Path, query: str) -> list[str]:
    """One line per matching document: its path and the text around the first match. Names match too."""
    needle = query.strip().casefold()
    if not needle:
        raise ValueError('"query" is empty')
    hits: list[str] = []
    for path in files(root):
        rel = path.relative_to(root).as_posix()
        try:
            text = text_of(path)
        except (OSError, ValueError):
            text = ""
        at = text.casefold().find(needle)
        if at < 0 and needle not in rel.casefold():
            continue
        snippet = (
            " ".join(text[max(0, at - SNIPPET) : at + len(needle) + SNIPPET].split())
            if at >= 0
            else ""
        )
        hits.append(f"{rel}: {snippet}" if snippet else rel)
        if len(hits) >= HITS_MAX:
            break
    return hits
