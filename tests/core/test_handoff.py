"""One-click handoff: a note in the vault's Handoffs folder and an inbox message to the receiver."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

import core.__main__ as sidecar
from core import added_agents, handoff
from core.settings import Settings


def test_the_note_has_the_users_words_open_tasks_calls_and_pins() -> None:
    text = handoff.compose(
        datetime(2026, 11, 23, 14, 5),
        "Ada",
        "Bo",
        "Finish the release notes.",
        [{"id": "K-1", "title": "Release", "status": "doing"}],
        [{"tool": "Bash", "status": "done", "detail": "npm test"}],
        ["Projects/Release.md"],
    )
    assert "# Handoff from Ada to Bo" in text
    assert "Finish the release notes." in text
    assert "- K-1 Release (doing)" in text
    assert "- Bash (done): npm test" in text
    assert "- [[Projects/Release]]" in text


def test_a_handoff_writes_the_note_and_messages_the_receiver(
    tmp_path: Path, monkeypatch: Any
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# A\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "s", Settings(vault=vault))
    added_agents.save(session.agents_path, [{"id": "ada", "name": "Ada"}])
    session.dispatch({"method": "open", "vault": str(vault)})
    monkeypatch.setattr(sidecar.cli_sessions, "tool_trace", lambda agent, limit: [])
    answer = session.dispatch(
        {"method": "handoff", "from": "ada", "to": "hippoherman", "note": "Pick up K-1."}
    )
    assert answer["note"].startswith("Handoffs/") and answer["note"].endswith(
        "Ada to Hippoherman.md"
    )
    assert "Pick up K-1." in (vault / answer["note"]).read_text(encoding="utf-8")
    sent = list((session.hive_path / "hippoherman" / "inbox").glob("*.json"))
    message = json.loads(sent[0].read_text(encoding="utf-8"))
    assert message["subject"] == "Handoff from Ada" and message["work"] == "handoff"
    assert message["body"].startswith("The note: [[Handoffs/")
    with pytest.raises(ValueError, match="itself"):
        session.dispatch({"method": "handoff", "from": "ada", "to": "ada"})
    with pytest.raises(ValueError, match="exist"):
        session.dispatch({"method": "handoff", "from": "ada", "to": "nobody"})
