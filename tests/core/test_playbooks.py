"""Playbooks: a note in the Playbooks folder, its list items are the steps, and a run is one message."""

import json
from pathlib import Path

import pytest

import core.__main__ as sidecar
from core import playbooks
from core.settings import Settings

TEXT = """---
tags: [playbook]
---
# Weekly release

Run this every Friday.

1. Run the tests
2. Write the notes
- [ ] Tag the build
"""


def test_the_title_steps_and_context_come_from_the_note() -> None:
    found = playbooks.parse("Playbooks/release.md", TEXT)
    assert found["title"] == "Weekly release"
    assert found["steps"] == ["Run the tests", "Write the notes", "Tag the build"]
    assert found["context"] == ["Run this every Friday."]
    text = playbooks.message(found, "skip the docs")
    assert "1. Run the tests" in text and "Also: skip the docs" in text
    assert playbooks.is_playbook("Playbooks/release.md")
    assert not playbooks.is_playbook("Notes/release.md")


def test_running_a_playbook_sends_its_steps_to_the_agent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "Playbooks").mkdir(parents=True)
    (vault / "Playbooks" / "release.md").write_text(TEXT, encoding="utf-8")
    (vault / "Playbooks" / "empty.md").write_text("# Empty\n", encoding="utf-8")
    (vault / "other.md").write_text("1. not a playbook\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "s", Settings(vault=vault))
    session.dispatch({"method": "open", "vault": str(vault)})
    listed = session.dispatch({"method": "playbooks"})["playbooks"]
    assert [p["path"] for p in listed] == ["Playbooks/empty.md", "Playbooks/release.md"]
    answer = session.dispatch(
        {"method": "playbook_run", "path": "Playbooks/release.md", "agent": "hippoherman"}
    )
    assert answer["steps"] == 3
    sent = list((session.hive_path / "hippoherman" / "inbox").glob("*.json"))
    message = json.loads(sent[0].read_text(encoding="utf-8"))
    assert message["subject"] == "Playbook: Weekly release"
    with pytest.raises(ValueError, match="no steps"):
        session.dispatch(
            {"method": "playbook_run", "path": "Playbooks/empty.md", "agent": "hippoherman"}
        )
    with pytest.raises(ValueError, match="Playbooks folder"):
        session.dispatch({"method": "playbook_run", "path": "other.md", "agent": "hippoherman"})
