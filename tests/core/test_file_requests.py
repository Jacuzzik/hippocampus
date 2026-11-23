"""File-based requests: a JSON file in the hive's requests folder becomes an inbox message."""

import json
from pathlib import Path

import core.__main__ as sidecar
from core import file_requests
from core.settings import Settings


def _drop(folder: Path, name: str, data: object) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_a_good_file_is_sent_and_a_bad_one_moves_aside_with_the_reason(tmp_path: Path) -> None:
    folder = tmp_path / file_requests.FOLDER
    _drop(folder, "a.json", {"to": "ada", "subject": "Build", "body": "Run the build."})
    _drop(folder, "b.json", {"to": "nobody", "subject": "x", "body": "y"})
    sent: list[dict[str, str]] = []
    later = 10**10
    assert file_requests.process(tmp_path, {"ada"}, sent.append, later) == (1, 1)
    assert sent[0]["to"] == "ada" and sent[0]["priority"] == "normal"
    assert len(list((folder / ".done").glob("*.json"))) == 1
    failed = json.loads(next((folder / ".failed").glob("*.json")).read_text(encoding="utf-8"))
    assert failed["to"] == "nobody" and '"to" must be one of' in failed["error"]
    assert list(folder.glob("*.json")) == []


def test_a_file_still_being_written_waits(tmp_path: Path) -> None:
    _drop(tmp_path / file_requests.FOLDER, "a.json", {"to": "ada", "subject": "s", "body": "b"})
    assert file_requests.process(tmp_path, {"ada"}, lambda r: None) == (0, 0)


def test_the_session_turns_a_request_into_a_message(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings())
    path = _drop(
        session.hive_path / file_requests.FOLDER,
        "r.json",
        {
            "to": "hippoherman",
            "subject": "Nightly",
            "body": "Check the links.",
            "priority": "urgent",
        },
    )
    import os

    os.utime(path, (1, 1))
    session._take_requests()
    sent = list((session.hive_path / "hippoherman" / "inbox").glob("*.json"))
    message = json.loads(sent[0].read_text(encoding="utf-8"))
    assert message["subject"] == "Nightly" and message["priority"] == "urgent"
