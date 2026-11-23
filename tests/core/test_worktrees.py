"""A git worktree per agent: on moves the agent to its own branch folder, off moves it back."""

import subprocess
from pathlib import Path

import pytest

import core.__main__ as sidecar
from core import added_agents
from core.settings import Settings


def _repo(path: Path) -> Path:
    (path / "src").mkdir(parents=True)
    (path / "src" / "a.txt").write_text("a", encoding="utf-8")
    for args in (
        ["init", "-q"],
        ["config", "user.email", "test@example.com"],
        ["config", "user.name", "Test"],
        ["add", "."],
        ["commit", "-q", "-m", "first"],
    ):
        subprocess.run(["git", *args], cwd=path, check=True)
    return path


def test_on_and_off_move_the_agent_and_keep_the_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "proj")
    session = sidecar.Session(tmp_path / "s", Settings())
    added_agents.save(
        session.agents_path, [{"id": "ada", "name": "Ada", "folder": str(repo / "src")}]
    )
    moved = session.dispatch({"method": "agent_worktree", "agent": "ada", "on": True})["agent"]
    assert moved["folder"] == str(tmp_path / "proj-worktrees" / "ada" / "src")
    assert (Path(moved["folder"]) / "a.txt").is_file() and moved["branch"] == "agent/ada"
    with pytest.raises(ValueError, match="already"):
        session.dispatch({"method": "agent_worktree", "agent": "ada", "on": True})
    # A change that is not committed keeps the worktree.
    (Path(moved["folder"]) / "a.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="not committed"):
        session.dispatch({"method": "agent_worktree", "agent": "ada", "on": False})
    subprocess.run(["git", "checkout", "--", "a.txt"], cwd=moved["folder"], check=True)
    back = session.dispatch({"method": "agent_worktree", "agent": "ada", "on": False})["agent"]
    assert back["folder"] == str(repo / "src") and "worktree_of" not in back
    branches = subprocess.run(
        ["git", "branch", "--list", "agent/ada"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert "agent/ada" in branches
    # On again reuses the kept branch.
    again = session.dispatch({"method": "agent_worktree", "agent": "ada", "on": True})["agent"]
    assert again["branch"] == "agent/ada"


def test_a_folder_outside_git_is_refused(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path / "s", Settings())
    plain = tmp_path / "plain"
    plain.mkdir()
    added_agents.save(session.agents_path, [{"id": "bo", "name": "Bo", "folder": str(plain)}])
    with pytest.raises(ValueError, match="not inside a git repository"):
        session.dispatch({"method": "agent_worktree", "agent": "bo", "on": True})
