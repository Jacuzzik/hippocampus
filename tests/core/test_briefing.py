from pathlib import Path
from typing import Any

import pytest

from core import __main__ as sidecar
from core import briefing, inbox
from core.settings import Settings

LIMITS = ["Shell: not available to this agent."]


def finished(text: str) -> str:
    return briefing.finish(text, Path("/tmp/inbox.md"), LIMITS)[0]


def test_both_briefings_pass_their_own_lint() -> None:
    main = finished(briefing.main_briefing("/vault"))
    agent = finished(
        briefing.agent_briefing(
            "ada#1",
            {"name": "Ada", "goal": "Tidy notes"},
            "/work/ada",
            "/vault",
            Path("/hive/ada#1/outbox"),
        )
    )
    assert briefing.lint(main) == [] and briefing.lint(agent) == []
    # The added sections carry on from each text's own last number.
    assert "11. Start-up inbox" in main and "12. Tools and limits in force" in main
    assert "12. Start-up inbox" in agent and "13. Tools and limits in force" in agent


def test_the_name_job_goal_and_folder_reach_the_agents_briefing() -> None:
    saved = {"name": "Ada", "description": "Breaks big tasks down", "goal": "Tidy the inbox notes"}
    outbox = Path("/hive/ada#1/outbox")
    text = briefing.agent_briefing("ada#1", saved, "/work/ada", "/vault", outbox)
    for part in (
        "You are Ada,",
        "Breaks big tasks down",
        "Tidy the inbox notes",
        "/work/ada",
        "/vault",
        "ada#1-PriorityNotes",
    ):
        assert part in text
    # The message format and the example are the inbox schema's own text.
    assert inbox.FORMAT_HELP in text and '"act": "done"' in text and str(outbox) in text


def test_the_stamp_changes_when_the_text_does() -> None:
    one, mark_one = briefing.finish(briefing.main_briefing("/vault"), Path("/i.md"), LIMITS)
    two, mark_two = briefing.finish(briefing.main_briefing("/other"), Path("/i.md"), LIMITS)
    assert mark_one["version"] == briefing.VERSION and mark_one["hash"] != mark_two["hash"]
    assert one.endswith(f"Briefing v{briefing.VERSION} · {mark_one['hash']}")


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (lambda text: text.replace("3. Limits", "Limits"), "out of order or one is missing"),
        (lambda text: "Intro\n" + text, "does not start with section 1"),
        (lambda text: text + "\nx" * briefing.SIZE_MAX, "most allowed"),
        (lambda text: text + "\nkey sk-ant-abcdef1234567890", "looks like a key"),
        (lambda text: text + "\nYour folder: {folder}", "never filled in"),
    ],
)
def test_the_lint_names_each_problem(change: Any, problem: str) -> None:
    text = change(finished(briefing.main_briefing("/vault")))
    assert any(problem in line for line in briefing.lint(text))


class FakeTerminals:
    def __init__(self) -> None:
        self.briefings: list[str] = []

    def start(
        self,
        agent: str,
        provider: str,
        rows: int,
        cols: int,
        model: str,
        folder: Any,
        text: str,
        *rest: Any,
    ) -> dict[str, Any]:
        self.briefings.append(text)
        return {"running": True, "replay": ""}

    def info(self, agent: str) -> dict[str, Any]:
        return {"command": None, "status": None}


def test_a_start_hands_the_cli_one_briefing_and_the_card_can_show_its_stamp(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session.terminals = FakeTerminals()  # type: ignore[assignment]
    for agent in ("hippoherman", "ada"):
        session.dispatch(
            {
                "method": "terminal_start",
                "agent": agent,
                "provider": "claude",
                "rows": 24,
                "cols": 80,
            }
        )
    main, ada = session.terminals.briefings
    assert main.startswith("1. Role\nYou are Hippoherman") and ada.startswith(
        "1. Role\nYou are ada,"
    )
    assert main.count("Tools and limits in force") == 1  # added once, not once per layer
    stamp = session.dispatch({"method": "terminal_command", "agent": "ada"})["briefing"]
    assert stamp["version"] == briefing.VERSION and ada.endswith(stamp["hash"]) and stamp["at"]


def test_an_agent_whose_goal_holds_a_key_is_not_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session.terminals = FakeTerminals()  # type: ignore[assignment]
    monkeypatch.setattr(
        sidecar.added_agents,
        "load",
        lambda path: [{"id": "ada", "name": "Ada", "goal": "use sk-ant-abcdef1234567890"}],
    )
    with pytest.raises(ValueError, match="cannot start.*looks like a key"):
        session.dispatch(
            {
                "method": "terminal_start",
                "agent": "ada",
                "provider": "claude",
                "rows": 24,
                "cols": 80,
            }
        )
    assert session.terminals.briefings == []
