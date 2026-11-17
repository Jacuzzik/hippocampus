"""The GitHub dashboard reads one repository with the gh CLI, read only."""

import json
import subprocess
from types import SimpleNamespace

from core.github_board import board


def _found(_name: str) -> str:
    return "/usr/bin/gh"


def _gh(answers: dict[str, str], calls: list[list[str]] | None = None):
    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if calls is not None:
            calls.append(command)
        return SimpleNamespace(returncode=0, stdout=answers[command[1]], stderr="")

    return run


ANSWERS = {
    "pr": json.dumps(
        [
            {"number": 7, "title": "Add dashboards", "isDraft": False},
            {"number": 6, "title": "Tidy tokens", "isDraft": True},
        ]
    ),
    "issue": json.dumps([{"number": 3, "title": "Graph is slow"}]),
    "run": json.dumps(
        [
            {"name": "tests", "status": "completed", "conclusion": "failure", "headBranch": "main"},
            {"name": "tests", "status": "in_progress", "conclusion": None, "headBranch": "dev"},
            {"name": "tests", "status": "completed", "conclusion": "success", "headBranch": "main"},
        ]
    ),
}


def test_counts_and_newest_rows_come_from_three_read_only_commands() -> None:
    calls: list[list[str]] = []
    found = board("octocat/hello-world", _found, _gh(ANSWERS, calls))
    assert found["pulls"] == 2
    assert found["drafts"] == 1
    assert found["issues"] == 1
    assert (found["runs"], found["failed_runs"], found["running_runs"]) == (3, 1, 1)
    assert found["newest_run"] == {"name": "tests", "branch": "main", "state": "failed"}
    assert found["newest_pulls"][0] == {"number": 7, "title": "Add dashboards"}
    assert found["capped"] == []
    assert [call[1:3] for call in calls] == [["pr", "list"], ["issue", "list"], ["run", "list"]]
    assert all(call[call.index("--repo") + 1] == "octocat/hello-world" for call in calls)


def test_a_repository_that_is_not_owner_slash_name_is_refused_before_gh_runs() -> None:
    def never(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("gh must not run")

    for bad in (
        "",
        "hello",
        "a/b/c",
        "octocat/hello world",
        "--repo x/y",
        "x/y; rm -rf ~",
        None,
        7,
    ):
        assert "owner/name" in board(bad, _found, never)["error"]


def test_missing_gh_a_failed_command_and_a_timeout_each_say_what_happened() -> None:
    assert "not installed" in board("a/b", lambda _name: None)["error"]

    def failing(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 404: Not Found")

    assert board("a/b", _found, failing) == {"error": "HTTP 404: Not Found"}

    def slow(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("gh", 30)

    assert board("a/b", _found, slow) == {"error": "GitHub took too long to answer."}

    def junk(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="not json", stderr="")

    assert "could not read" in board("a/b", _found, junk)["error"]


def test_an_empty_repository_has_zero_counts_and_no_newest_run() -> None:
    found = board("a/b", _found, _gh({"pr": "[]", "issue": "[]", "run": "[]"}))
    assert (found["pulls"], found["issues"], found["runs"]) == (0, 0, 0)
    assert found["newest_run"] is None


def test_a_full_list_is_marked_as_possibly_cut_short() -> None:
    many = json.dumps([{"number": n, "title": "x", "isDraft": False} for n in range(100)])
    found = board("a/b", _found, _gh({"pr": many, "issue": "[]", "run": "[]"}))
    assert found["capped"] == ["pulls"]


def test_a_cancelled_or_skipped_run_is_not_counted_as_failed() -> None:
    runs = json.dumps(
        [
            {"name": "ci", "status": "completed", "conclusion": "cancelled", "headBranch": "main"},
            {"name": "ci", "status": "completed", "conclusion": "skipped", "headBranch": "main"},
            {"name": "ci", "status": "completed", "conclusion": "timed_out", "headBranch": "main"},
        ]
    )
    found = board("a/b", _found, _gh({"pr": "[]", "issue": "[]", "run": runs}))
    assert found["failed_runs"] == 1
    assert found["newest_run"]["state"] == "cancelled"
