"""A git worktree per agent (7.06): an added agent can work in its own branch folder, so agents
working in parallel on one repository do not collide.

Turning it on finds the repository that holds the agent's folder, adds a worktree for the branch
agent/<id> beside the repository (in "<repo>-worktrees/<id>"), and moves the agent to the same
place inside it. Turning it off removes that worktree, which git refuses while it holds changes that
are not committed, and moves the agent back. The branch itself is kept, so no work is lost.
"""

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

SECONDS = 60
SAFE = re.compile(r"[^A-Za-z0-9._-]+")
Run = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (fixed git arguments)
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=SECONDS, check=False
    )


def branch_for(agent: str) -> str:
    return "agent/" + (SAFE.sub("-", agent).strip("-.") or "agent")


def create(folder: Path, agent: str, run: Run = _git) -> tuple[Path, str]:
    """Returns the agent's new folder inside the worktree, and the branch."""
    top = run(["rev-parse", "--show-toplevel"], folder)
    if top.returncode != 0:
        raise ValueError("This agent's folder is not inside a git repository.")
    root = Path(top.stdout.strip()).resolve()
    inside = folder.resolve().relative_to(root)
    target = root.parent / f"{root.name}-worktrees" / SAFE.sub("-", agent).strip("-.")
    branch = branch_for(agent)
    if target.exists():
        raise ValueError(f"{target} already exists; remove it or pick another agent.")
    has_branch = run(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root)
    args = (
        ["worktree", "add", str(target), branch]
        if has_branch.returncode == 0
        else [
            "worktree",
            "add",
            "-b",
            branch,
            str(target),
        ]
    )
    made = run(args, root)
    if made.returncode != 0:
        raise ValueError(f"git worktree add failed: {made.stderr.strip()[:300]}")
    return target / inside, branch


def remove(worktree_folder: Path, run: Run = _git) -> None:
    top = run(["rev-parse", "--show-toplevel"], worktree_folder)
    common = run(["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree_folder)
    if top.returncode != 0 or common.returncode != 0:
        raise ValueError("The agent's worktree is not there any more.")
    target = Path(top.stdout.strip())
    main = Path(common.stdout.strip()).parent
    gone = run(["worktree", "remove", str(target)], main)
    if gone.returncode != 0:
        said = gone.stderr.strip()
        if "modified or untracked" in said or "is dirty" in said:
            raise ValueError(
                "git kept the worktree: it has changes that are not committed. Commit or"
                " discard them first."
            )
        raise ValueError(f"git worktree remove failed: {said[:300]}")
