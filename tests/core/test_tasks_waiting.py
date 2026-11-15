"""The task board says which cards hold a question for the human that has no answer yet."""

import json
from pathlib import Path

import pytest

from core.__main__ import Session
from core.settings import Settings


def test_a_card_with_an_open_question_waits_on_the_human(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board = tmp_path / "tasks.json"
    board.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "V-1",
                        "title": "Open",
                        "status": "blocked",
                        "humanQA": [{"q": "Which?"}],
                    },
                    {
                        "id": "V-2",
                        "title": "Answered",
                        "status": "doing",
                        "humanQA": [{"q": "Which?", "a": "The first"}],
                    },
                    {"id": "V-3", "title": "Plain", "status": "todo"},
                    {"id": "V-4", "title": "Odd", "status": "todo", "humanQA": "not a list"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MD_TASKS_FILE", str(board))
    session = Session(
        storage=tmp_path / "storage",
        settings=Settings(),
        settings_path=tmp_path / "settings.toml",
    )
    waiting = {t["id"]: t["waiting"] for t in session.tasks()["tasks"]}
    assert waiting == {"V-1": True, "V-2": False, "V-3": False, "V-4": False}
