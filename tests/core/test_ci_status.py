"""The Monitor tab can ask for the newest CI run of a folder's repo."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from core.session_shared import ci_in


def _gh(stdout: str = "[]", code: int = 0, stderr: str = ""):
    return lambda *a, **k: SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def _found(_name: str) -> str:
    return "/usr/bin/gh"


def test_a_finished_run_is_passed_or_failed(tmp_path: Path) -> None:
    ok = json.dumps(
        [{"name": "tests", "status": "completed", "conclusion": "success", "headBranch": "main"}]
    )
    bad = json.dumps(
        [{"name": "tests", "status": "completed", "conclusion": "failure", "headBranch": "main"}]
    )
    assert ci_in(str(tmp_path), _found, _gh(ok)) == {
        "state": "passed",
        "text": "tests on main: passed.",
    }
    assert ci_in(str(tmp_path), _found, _gh(bad)) == {
        "state": "failed",
        "text": "tests on main: failure.",
    }


def test_a_run_in_progress_and_a_repo_with_no_runs(tmp_path: Path) -> None:
    going = json.dumps(
        [{"name": "tests", "status": "in_progress", "conclusion": None, "headBranch": "dev"}]
    )
    assert ci_in(str(tmp_path), _found, _gh(going))["state"] == "running"
    assert ci_in(str(tmp_path), _found, _gh("[]"))["state"] == "none"


def test_problems_come_back_as_plain_errors(tmp_path: Path) -> None:
    assert "does not exist" in ci_in(str(tmp_path / "nope"), _found, _gh())["error"]
    assert "not installed" in ci_in(str(tmp_path), lambda _n: None, _gh())["error"]
    assert (
        ci_in(str(tmp_path), _found, _gh(code=1, stderr="not a git repo"))["error"]
        == "not a git repo"
    )
    assert "could not read" in ci_in(str(tmp_path), _found, _gh("not json"))["error"]

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("gh", 30)

    assert "too long" in ci_in(str(tmp_path), _found, slow)["error"]
