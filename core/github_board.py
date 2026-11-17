"""What the GitHub dashboard shows for one repository, read with the gh CLI the user is logged in to.

Read only: three `gh ... list` commands with a time limit. Nothing is written and no token is handled
here; gh keeps its own login.
"""

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")
SECONDS = 30
LIMIT = 100
FAILED = ("failure", "timed_out", "startup_failure")
READS = {
    "pulls": ["pr", "list", "--state", "open", "--json", "number,title,isDraft"],
    "issues": ["issue", "list", "--state", "open", "--json", "number,title"],
    "runs": ["run", "list", "--json", "name,status,conclusion,headBranch"],
}


def _rows(repo: str, args: list[str], run: Callable[..., Any]) -> list[dict[str, Any]]:
    done = run(
        ["gh", *args, "--repo", repo, "--limit", str(LIMIT)],
        capture_output=True,
        text=True,
        timeout=SECONDS,
        check=False,
    )
    if done.returncode != 0:
        raise ValueError(done.stderr.strip() or "gh could not read that repository.")
    try:
        found = json.loads(done.stdout or "[]")
    except ValueError as error:
        raise ValueError("gh gave an answer this app could not read.") from error
    return [row for row in found if isinstance(row, dict)]


def _run_state(row: dict[str, Any]) -> str:
    if row.get("status") != "completed":
        return "running"
    conclusion = str(row.get("conclusion") or "")
    if conclusion == "success":
        return "passed"
    # A cancelled or skipped run is not a failure; it keeps its own word.
    return "failed" if conclusion in FAILED else conclusion or "unknown"


def board(
    repo: object,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Counts and the newest few rows of a repository, or {"error": ...} saying what to do."""
    if not isinstance(repo, str) or not REPO.match(repo.strip()):
        return {"error": "Write the repository as owner/name, for example octocat/hello-world."}
    repo = repo.strip()
    if which("gh") is None:
        return {"error": "The gh CLI is not installed. Install it, then run `gh auth login`."}
    try:
        pulls = _rows(repo, READS["pulls"], run)
        issues = _rows(repo, READS["issues"], run)
        runs = _rows(repo, READS["runs"], run)
    except subprocess.TimeoutExpired:
        return {"error": "GitHub took too long to answer."}
    except ValueError as error:
        return {"error": str(error)}
    states = [_run_state(row) for row in runs]
    newest = runs[0] if runs else None
    return {
        "repo": repo,
        "pulls": len(pulls),
        "drafts": sum(1 for row in pulls if row.get("isDraft")),
        "issues": len(issues),
        "runs": len(runs),
        "failed_runs": states.count("failed"),
        "running_runs": states.count("running"),
        "newest_run": (
            {
                "name": str(newest.get("name") or "CI"),
                "branch": str(newest.get("headBranch") or "unknown branch"),
                "state": states[0],
            }
            if newest
            else None
        ),
        "newest_pulls": [
            {"number": row.get("number"), "title": str(row.get("title") or "")} for row in pulls[:5]
        ],
        "newest_issues": [
            {"number": row.get("number"), "title": str(row.get("title") or "")}
            for row in issues[:5]
        ],
        # A list as long as the limit may be cut short, so the count is "at least".
        "capped": [
            name for name, rows in (("pulls", pulls), ("issues", issues)) if len(rows) >= LIMIT
        ],
    }
