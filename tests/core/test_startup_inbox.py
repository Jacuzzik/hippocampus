from pathlib import Path

from core import inbox, startup_inbox

AGENTS = [
    {"id": "hippoherman", "name": "Hippoherman", "goal": "coordinate"},
    {"id": "Brooke#1", "name": "Brooke", "goal": "keep meeting decisions"},
    {"id": "Walter#2", "name": "Walter", "goal": "answer questions"},
]


def test_lists_own_waiting_messages_only(tmp_path: Path) -> None:
    hive = tmp_path / "hive"
    inbox.send(hive, "hippoherman", "Brooke#1", "Make notes", "Summarise the call")
    inbox.send(hive, "hippoherman", "Walter#2", "Other task", "not for Brooke")
    text = startup_inbox.build(hive, "Brooke#1", AGENTS)
    assert "request from hippoherman: Make notes" in text
    # The body is typed in full by the delivery loop, so it is not repeated here.
    assert "Summarise the call" not in text
    assert "Other task" not in text


def test_lists_other_agents_not_self(tmp_path: Path) -> None:
    text = startup_inbox.build(tmp_path / "hive", "Brooke#1", AGENTS)
    assert "Walter#2" in text
    assert "keep meeting decisions" not in text.split("## Agents you can message")[1].split("## How")[0]


def test_report_and_send_instructions_present(tmp_path: Path) -> None:
    text = startup_inbox.build(tmp_path / "hive", "Brooke#1", AGENTS)
    assert "DONE:" in text and "BLOCKED:" in text and "QUESTION:" in text
    assert '"to"' in text and '"subject"' in text and '"body"' in text
    # The format and the example come from the schema, so they cannot drift from it.
    assert inbox.FORMAT_HELP in text and '"act": "done"' in text


def test_main_agent_gets_reading_policy(tmp_path: Path) -> None:
    hippoherman = startup_inbox.build(tmp_path / "hive", "hippoherman", AGENTS)
    brooke = startup_inbox.build(tmp_path / "hive", "Brooke#1", AGENTS)
    assert "Act on BLOCKED and QUESTION reports" in hippoherman
    assert "Act on BLOCKED and QUESTION reports" not in brooke


def test_write_creates_file_in_briefings(tmp_path: Path) -> None:
    hive = tmp_path / "hive"
    path = startup_inbox.write(hive, "Brooke#1", AGENTS)
    assert path == tmp_path / "briefings" / "Brooke#1-inbox.md"
    assert path.read_text(encoding="utf-8").startswith("# Start-up inbox for Brooke#1")
