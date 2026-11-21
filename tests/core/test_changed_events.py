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
