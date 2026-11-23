"""The GitHub dashboard: every repository of the signed-in user, and what the app's agents did in each.

Repositories come from the gh CLI the user is signed in to (read only). The agents' work comes from the
git history of each agent's own folder on this computer: a folder whose remote is a GitHub repository
counts as that agent working there. Nothing is written anywhere.
"""

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

SECONDS = 30
LIMIT = 200
DAYS = 30
REMOTE = re.compile(r"github\.com[:/]([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?/?$")
FIELDS = "nameWithOwner,description,isPrivate,isFork,pushedAt,url,primaryLanguage,stargazerCount"


def repos(
    which: Callable[[str], str | None] = shutil.which, run: Callable[..., Any] = subprocess.run
) -> list[dict[str, Any]]:
    if which("gh") is None:
        raise ValueError(
            "The GitHub CLI (gh) is not installed. Install it, then run gh auth login."
        )
    done = run(
        ["gh", "repo", "list", "--limit", str(LIMIT), "--json", FIELDS],
        capture_output=True,
        text=True,
        timeout=SECONDS,
        check=False,
    )
    if done.returncode != 0:
        reason = (done.stderr or "").strip()
        if "auth" in reason.lower() or "log in" in reason.lower() or "logged" in reason.lower():
            raise ValueError(
                "gh is not signed in. Run gh auth login in a terminal, then press Refresh."
            )
        raise ValueError(reason or "gh could not list your repositories.")
    rows = json.loads(done.stdout or "[]")
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("nameWithOwner"):
            continue
        out.append(
            {
                "repo": row["nameWithOwner"],
                "description": row.get("description") or "",
                "private": bool(row.get("isPrivate")),
                "fork": bool(row.get("isFork")),
                "pushed": row.get("pushedAt") or "",
                "url": row.get("url") or "",
                "language": (row.get("primaryLanguage") or {}).get("name", "")
                if isinstance(row.get("primaryLanguage"), dict)
                else "",
                "stars": int(row.get("stargazerCount") or 0),
            }
        )
    out.sort(key=lambda r: r["pushed"], reverse=True)
    return out


def _git(folder: Path, *args: str, run: Callable[..., Any]) -> str:
    done = run(
        ["git", "-C", str(folder), *args],
        capture_output=True,
        text=True,
        timeout=SECONDS,
        check=False,
    )
    return done.stdout if done.returncode == 0 else ""


def agent_work(
    agents: list[tuple[str, str, Path]], run: Callable[..., Any] = subprocess.run
) -> dict[str, list[dict[str, Any]]]:
    """repo -> one row per agent that has a folder on it: commits in 30 days and the newest subjects."""
    work: dict[str, list[dict[str, Any]]] = {}
    for agent_id, name, folder in agents:
        if not (folder / ".git").exists():
            continue
        found = REMOTE.search(_git(folder, "remote", "get-url", "origin", run=run).strip())
        if not found:
            continue
        log = _git(
            folder, "log", f"--since={DAYS}.days", "--format=%ad%x09%s", "--date=short", run=run
        )
        commits = [line.split("\t", 1) for line in log.splitlines() if "\t" in line]
        work.setdefault(found.group(1), []).append(
            {
                "agent": agent_id,
                "name": name,
                "folder": str(folder),
                "commits": len(commits),
                "last": commits[0][0] if commits else "",
                "subjects": [subject for _, subject in commits[:5]],
            }
        )
    return work


def board(
    agents: list[tuple[str, str, Path]],
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """All repositories with the agents' work on each, or {"error": ...} saying what to do."""
    try:
        found = repos(which, run)
    except (ValueError, subprocess.TimeoutExpired) as error:
        return {
            "error": str(error) if isinstance(error, ValueError) else "gh took too long to answer."
        }
    work = agent_work(agents, run)
    for row in found:
        row["agents"] = work.pop(row["repo"], [])
    # Agents working on a repository not in the list (someone else's) are still shown.
    others = [
        {"repo": repo, "agents": rows, "foreign": True} for repo, rows in sorted(work.items())
    ]
    return {"repos": found, "others": others, "days": DAYS}
