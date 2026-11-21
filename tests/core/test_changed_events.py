"""The backend tells the window when the activity log or the inboxes change, so panels need no fast timer."""

from pathlib import Path
from typing import Any

import core.__main__ as sidecar
from core.settings import Settings


def test_a_new_activity_line_and_a_sent_message_each_push_a_changed_event(tmp_path: Path) -> None:
    events: list[dict[str, Any]] = []
    session = sidecar.Session(tmp_path, Settings(), emit=events.append)
    session.note("setting", text="something changed")
    assert {"event": "changed", "what": "activity"} in events
    events.clear()
    session.dispatch(
        {"method": "task_send", "to": "hippoherman", "from": "user", "subject": "s", "body": "b"}
    )
    assert {"event": "changed", "what": "inbox"} in events


def test_questions_approvals_and_helpers_push_changed_events(tmp_path: Path) -> None:
    events: list[dict[str, Any]] = []
    session = sidecar.Session(tmp_path, Settings(), emit=events.append)

    def seen(what: str) -> bool:
        found = {"event": "changed", "what": what} in events
        events.clear()
        return found

    session.asks.open("a1", "Which folder?")
    assert seen("asks")
    session.asks.answer("a1", "notes")
    assert seen("asks")
    session.gate.open("c1", "note_write", "preview")
    assert seen("asks")
    session.gate.decide("c1", True)
    assert seen("asks")
    session.helpers._on_event({"text": "helper 1 started"})
    assert seen("helpers")


def test_saving_deleting_and_colouring_a_note_push_a_notes_event(tmp_path: Path) -> None:
    events: list[dict[str, Any]] = []
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# A\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "s", Settings(vault=vault), emit=events.append)
    session.dispatch({"method": "open", "vault": str(vault)})
    events.clear()
    session.dispatch({"method": "note_save", "path": "a.md", "text": "# A\nmore\n"})
    assert {"event": "changed", "what": "notes"} in events
