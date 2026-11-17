"""Tasks go out as four-part contracts (8.05)."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from core import __main__ as sidecar
from core import briefing, contract, inbox
from core.settings import Settings


def test_a_contract_has_four_parts_and_defaults_fill_the_empty_ones() -> None:
    text = contract.build({"objective": "Tidy the inbox", "tools": "Only the vault tools"})
    assert [line for line in text.splitlines() if line.startswith("## ")] == [
        "## Objective",
        "## Output",
        "## Tools",
        "## Boundaries",
    ]
    assert "Tidy the inbox" in text and "Only the vault tools" in text
    assert contract.DEFAULTS["Boundaries"] in text
    with pytest.raises(ValueError, match="objective"):
        contract.build({"output": "x"})


def test_wrap_does_not_wrap_twice() -> None:
    once = contract.wrap("Check the links")
    assert contract.is_contract(once) and contract.wrap(once) == once


def test_every_briefing_says_tasks_are_contracts(tmp_path: Path) -> None:
    rule = "Tasks are contracts"
    assert rule in briefing.main_briefing(None, tmp_path / "outbox")
    assert rule in briefing.agent_briefing("ada", {"name": "Ada"}, None, None, tmp_path / "o")


def test_a_temp_gets_its_task_as_a_contract(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    sent: list[str] = []

    class Helpers:
        def start(self, prompt: str) -> dict[str, Any]:
            sent.append(prompt)
            return {}

    session.helpers = Helpers()  # type: ignore[assignment]
    session.helpers_state = lambda: {}  # type: ignore[method-assign]
    session.start_helper({"prompt": "Fix the broken links"})
    session.start_helper({"parts": {"objective": "Sum the notes", "output": "One number"}})
    assert all(contract.is_contract(p) for p in sent)
    assert "One number" in sent[1]
    session.close()


def test_a_mission_message_arrives_as_a_contract(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session.dispatch(
        {
            "method": "mission_save",
            "mission": {
                "label": "Check",
                "message": "Check the inbox",
                "agent": "hippoherman",
                "every_minutes": 60,
                "enabled": True,
            },
        }
    )
    session.run_missions(datetime(2026, 11, 16, 10, 0))
    [(_, message)] = inbox.pending(session.hive_path, "hippoherman")
    assert contract.is_contract(message["body"]) and "Check the inbox" in message["body"]
    session.close()


def test_a_description_ending_in_a_full_stop_gets_one_full_stop(tmp_path: Path) -> None:
    text = briefing.agent_briefing(
        "ada",
        {"name": "Ada", "description": "Keeps notes tidy.", "goal": "Merge."},
        None,
        None,
        tmp_path,
    )
    assert "Keeps notes tidy. " in text and ".." not in text
