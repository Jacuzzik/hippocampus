"""One committer: an agent's commit request is committed by the app, only its paths, one at a time."""

import json
import subprocess
from pathlib import Path

import pytest

from core import commit_queue

LATER = 10**10


def _repo(path: Path) -> Path:
    path.mkdir()
    for args in (
        ["init", "-q"],
        ["config", "user.email", "test@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(["git", *args], cwd=path, check=True)
    return path


def _ask(hive: Path, name: str, data: object) -> None:
    folder = hive / commit_queue.FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


def test_only_the_named_paths_are_committed(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    (repo / "a.md").write_text("a", encoding="utf-8")
    (repo / "b.md").write_text("b", encoding="utf-8")
    hive = tmp_path / "hive"
    _ask(hive, "1.json", {"from": "ada", "repo": str(repo), "paths": ["a.md"], "message": "Add a"})
    lines = commit_queue.process(hive, [repo], {"ada"}, now=LATER)
    assert lines[0].startswith("committed 1 file(s) for ada in repo: ")
    files = subprocess.run(
        ["git", "show", "--name-only", "--format=%B", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    ).stdout
    assert "a.md" in files and "b.md" not in files and "Asked by agent ada" in files
    done = json.loads(next((hive / "commits" / ".done").glob("*.json")).read_text(encoding="utf-8"))
    assert done["commit"]


@pytest.mark.parametrize(
    ("request_data", "reason"),
    [
        ({"from": "bo", "repo": "R", "paths": ["a.md"], "message": "m"}, '"from"'),
        ({"from": "ada", "repo": "/etc", "paths": ["a.md"], "message": "m"}, "vault or an agent"),
        ({"from": "ada", "repo": "R", "paths": ["../x.md"], "message": "m"}, "outside the repo"),
        ({"from": "ada", "repo": "R", "paths": ["--all"], "message": "m"}, "inside the repo"),
        ({"from": "ada", "repo": "R", "paths": ["a.md"], "message": " "}, '"message"'),
    ],
)
def test_a_bad_request_is_refused_with_the_reason(
    tmp_path: Path, request_data: dict[str, object], reason: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data = {
        **request_data,
        "repo": str(repo) if request_data["repo"] == "R" else request_data["repo"],
    }
    _ask(tmp_path, "1.json", data)
    lines = commit_queue.process(tmp_path, [repo], {"ada"}, now=LATER)
    assert lines[0].startswith("refused") and reason in lines[0]
    assert list((tmp_path / "commits" / ".failed").glob("*.json"))
