"""7.18: the built-in code editor's file and git work, all inside one agent folder.

Every path is resolved against the folder and refused if it leaves it (including through a symlink). Reads stop at
a size limit and refuse binary files. Git is run with fixed argument lists, never through a shell."""

import fnmatch
import subprocess
from pathlib import Path
from typing import Any

from core import safe_write

MAX_READ = 1_000_000
SKIP = {".git", "node_modules", "__pycache__", ".venv", "target", "dist", ".svelte-kit"}
_GIT_TIMEOUT = 15


def _root(folder: object) -> Path:
    if not isinstance(folder, (str, Path)) or not str(folder) or not Path(folder).is_dir():
        raise ValueError("the agent's folder does not exist yet")
    return Path(folder).resolve()


def inside(folder: object, rel: object, *, must_exist: bool = True) -> Path:
    root = _root(folder)
    if not isinstance(rel, str) or "\0" in rel:
        raise ValueError("A file path is needed.")
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise ValueError("That path is outside the agent's folder.")
    if must_exist and not target.exists():
        raise ValueError(f"{rel} does not exist.")
    return target


def tree(folder: object, rel: str = "") -> list[dict[str, Any]]:
    """One level of a directory: folders first, then files. Hidden build folders are left out."""
    base = inside(folder, rel)
    if not base.is_dir():
        raise ValueError(f"{rel} is not a folder.")
    root = _root(folder)
    rows = []
    for item in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if item.name in SKIP:
            continue
        rows.append(
            {"name": item.name, "path": item.relative_to(root).as_posix(), "dir": item.is_dir()}
        )
    return rows


def search(folder: object, query: object, glob: object = "*") -> list[dict[str, Any]]:
    """Search text files below one agent folder without entering generated or git data."""
    if not isinstance(query, str) or not query:
        raise ValueError("Enter text to search for.")
    if not isinstance(glob, str) or not glob or "/" in glob or "\\" in glob:
        raise ValueError("Use a file name pattern such as *.py.")
    root = _root(folder)
    matches: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in SKIP for part in rel.parts):
            continue
        try:
            path = inside(root, rel.as_posix())
        except ValueError:
            continue
        if not path.is_file():
            continue
        if not fnmatch.fnmatch(path.name, glob) or path.stat().st_size > MAX_READ:
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if query.casefold() in line.casefold():
                matches.append(
                    {"path": path.relative_to(root).as_posix(), "line": number, "text": line[:500]}
                )
                if len(matches) >= 500:
                    return matches
    return matches


def replace(
    folder: object, query: object, replacement: object, glob: object = "*"
) -> dict[str, Any]:
    """Replace text in matching files in the agent folder, returning changed paths."""
    if not isinstance(query, str) or not query:
        raise ValueError("Enter text to replace.")
    if not isinstance(replacement, str):
        raise ValueError("Enter replacement text.")
    root = _root(folder)
    changed: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in SKIP for part in rel.parts):
            continue
        try:
            path = inside(root, rel.as_posix())
        except ValueError:
            continue
        if not path.is_file():
            continue
        if not fnmatch.fnmatch(path.name, str(glob)) or path.stat().st_size > MAX_READ:
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", errors="replace")
        updated = text.replace(query, replacement)
        if updated != text:
            safe_write.write_text(path, updated)
            changed.append(rel.as_posix())
    return {"files": changed, "count": len(changed)}


def commit(folder: object, paths: object, message: object) -> dict[str, Any]:
    """Commit only the selected paths, after staging exactly those paths in this repository."""
    root = _root(folder)
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        raise ValueError("Choose at least one changed file.")
    if not isinstance(message, str) or not message.strip() or len(message) > 200:
        raise ValueError("Enter a commit message of 1 to 200 characters.")
    names = []
    for path in dict.fromkeys(paths):
        target = inside(root, path)
        relative = target.relative_to(root)
        if any(part in SKIP for part in relative.parts) or not target.is_file():
            raise ValueError("Choose files inside the agent's folder.")
        names.append(relative.as_posix())
    _git(root, "add", "--", *names)
    _git(root, "commit", "-m", message.strip(), "--", *names)
    return changes(root)


def read(folder: object, rel: object) -> dict[str, Any]:
    target = inside(folder, rel)
    if not target.is_file():
        raise ValueError(f"{rel} is not a file.")
    size = target.stat().st_size
    if size > MAX_READ:
        raise ValueError(
            f"{rel} is {size:,} bytes, over the {MAX_READ:,} byte limit for the editor."
        )
    data = target.read_bytes()
    if b"\0" in data[:8192]:
        raise ValueError(f"{rel} is not a text file.")
    return {"path": str(rel), "text": data.decode("utf-8", errors="replace"), "size": size}


def save(folder: object, rel: object, text: object) -> dict[str, Any]:
    if not isinstance(text, str):
        raise ValueError('"text" must be the file text')
    target = inside(folder, rel, must_exist=False)
    if target.is_dir():
        raise ValueError(f"{rel} is a folder.")
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(target, text)
    return {"path": str(rel), "size": len(text.encode("utf-8"))}


def _git(folder: object, *args: str) -> str:
    root = _root(folder)
    done = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=False,
    )
    if done.returncode != 0:
        raise ValueError(done.stderr.strip() or "git could not do that here")
    return done.stdout


def is_repo(folder: object) -> bool:
    try:
        return _git(folder, "rev-parse", "--is-inside-work-tree").strip() == "true"
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return False


def changes(folder: object) -> dict[str, Any]:
    if not is_repo(folder):
        return {"repo": False, "branch": "", "files": []}
    branch = _git(folder, "rev-parse", "--abbrev-ref", "HEAD").strip()
    files = []
    for line in _git(folder, "status", "--porcelain").splitlines():
        if len(line) > 3:
            files.append({"state": line[:2].strip() or "?", "path": line[3:].split(" -> ")[-1]})
    return {"repo": True, "branch": branch, "files": files}


def diff(folder: object, rel: object) -> str:
    target = inside(folder, rel)
    name = target.relative_to(_root(folder)).as_posix()
    text = _git(folder, "diff", "HEAD", "--", name)
    return text or "No changes against the last commit."


def history(folder: object, rel: object = "") -> list[dict[str, str]]:
    args = ["log", "-30", "--format=%h%x09%an%x09%ad%x09%s", "--date=short"]
    if rel:
        args += ["--", inside(folder, rel).relative_to(_root(folder)).as_posix()]
    rows = []
    for line in _git(folder, *args).splitlines():
        sha, author, when, subject = (line.split("\t", 3) + ["", "", "", ""])[:4]
        rows.append({"sha": sha, "author": author, "date": when, "subject": subject})
    return rows


def branches(folder: object) -> list[str]:
    return [
        b.strip()
        for b in _git(folder, "branch", "--format=%(refname:short)").splitlines()
        if b.strip()
    ]


def compare(folder: object, base: object, head: object) -> dict[str, Any]:
    known = set(branches(folder))
    if base not in known or head not in known:
        raise ValueError("Pick two branches that exist in this folder.")
    base, head = str(base), str(head)
    names = _git(folder, "diff", "--name-status", f"{base}...{head}").splitlines()
    files = [{"state": n.split("\t")[0], "path": n.split("\t")[-1]} for n in names if n.strip()]
    ahead = _git(folder, "rev-list", "--count", f"{base}..{head}").strip()
    behind = _git(folder, "rev-list", "--count", f"{head}..{base}").strip()
    return {"base": base, "head": head, "ahead": int(ahead), "behind": int(behind), "files": files}
