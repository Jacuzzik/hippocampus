"""One committer for shared files (7.11): agents ask, the app commits, one at a time.

An agent that wants files committed drops `commits/<name>.json` in the hive: {"from": "<agent id>",
"repo": "<folder>", "paths": ["a.md", ...], "message": "..."}. The delivery loop takes the requests
oldest first and runs `git add -- <paths>` then `git commit` in that folder, with only those paths,
so two agents never fight over the git index. The repo must be the vault or an agent's own folder,
every path must stay inside it, and nothing is pushed. A done request moves to commits/.done/ with
the commit id; a refused one to commits/.failed/ with the reason.
"""

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

FOLDER = "commits"
MAX_BYTES = 20_000
PATHS_MAX = 200
MESSAGE_MAX = 500
SETTLE_S = 1.0
GIT_SECONDS = 30
Run = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (fixed git arguments, paths checked to stay inside the repo)
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=GIT_SECONDS,
        check=False,
    )


def check(data: object, allowed: list[Path], known: set[str]) -> tuple[Path, list[str], str, str]:
    if not isinstance(data, dict):
        raise ValueError("A commit request is one JSON object.")
    sender = data.get("from")
    if not isinstance(sender, str) or sender not in known:
        raise ValueError('"from" must be the id of an agent.')
    repo_raw = data.get("repo")
    if not isinstance(repo_raw, str) or not repo_raw:
        raise ValueError('"repo" must be the folder to commit in.')
    repo = Path(repo_raw).expanduser().resolve()
    if not any(repo == root.resolve() for root in allowed):
        raise ValueError("The repo must be the vault or an agent's own folder.")
    paths = data.get("paths")
    if not isinstance(paths, list) or not paths or len(paths) > PATHS_MAX:
        raise ValueError(f'"paths" must list 1 to {PATHS_MAX} files.')
    clean: list[str] = []
    for raw in paths:
        if not isinstance(raw, str) or not raw.strip() or raw.startswith("-"):
            raise ValueError("Each path must be a file name inside the repo.")
        full = (repo / raw).resolve()
        if repo not in full.parents and full != repo:
            raise ValueError(f"{raw} is outside the repo.")
        clean.append(full.relative_to(repo).as_posix())
    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError('"message" must say what the commit does.')
    return repo, clean, message.strip()[:MESSAGE_MAX], sender


def commit(repo: Path, paths: list[str], message: str, sender: str, run: Run = _git) -> str:
    """Commit only `paths`. Returns the short commit id."""
    added = run(["add", "--", *paths], repo)
    if added.returncode != 0:
        raise ValueError(f"git add failed: {added.stderr.strip()[:300]}")
    done = run(
        [
            "commit",
            "-m",
            f"{message}\n\nAsked by agent {sender}, committed by Hippocampus.",
            "--",
            *paths,
        ],
        repo,
    )
    if done.returncode != 0:
        raise ValueError(f"git commit failed: {(done.stdout + done.stderr).strip()[:300]}")
    head = run(["rev-parse", "--short", "HEAD"], repo)
    return head.stdout.strip()


def _move(path: Path, folder: str, extra: dict[str, Any]) -> None:
    target = path.parent / folder
    target.mkdir(exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    name = f"{int(time.time() * 1000)}-{path.name}"
    (target / name).write_text(json.dumps({**data, **extra}, indent=2), encoding="utf-8")
    path.unlink(missing_ok=True)


def process(
    hive: Path,
    allowed: list[Path],
    known: set[str],
    run: Run = _git,
    now: float | None = None,
) -> list[str]:
    """Take every settled request, oldest first. One line per request, for the activity log."""
    folder = hive / FOLDER
    if not folder.is_dir():
        return []
    now = time.time() if now is None else now
    lines = []
    for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            if now - path.stat().st_mtime < SETTLE_S:
                continue
            if path.stat().st_size > MAX_BYTES:
                raise ValueError(f"The file is larger than {MAX_BYTES} bytes.")
            repo, paths, message, sender = check(
                json.loads(path.read_text(encoding="utf-8")), allowed, known
            )
            head = commit(repo, paths, message, sender, run)
        except FileNotFoundError:
            continue
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            _move(path, ".failed", {"error": str(error)})
            lines.append(f"refused a commit request: {error}")
            continue
        _move(path, ".done", {"commit": head})
        lines.append(f"committed {len(paths)} file(s) for {sender} in {repo.name}: {head}")
    return lines
