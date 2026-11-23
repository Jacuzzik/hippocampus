"""The live fleet file: one row per agent, written only when it changes, never with a command or key."""

import json
from pathlib import Path

import core.__main__ as sidecar
from core import fleet
from core.settings import Settings


def _info(agent: str) -> dict[str, object]:
    return {
        "a": {"status": "Working", "model": "opus", "command": "claude --secret-flag"},
        "b": {"status": None, "crashed": 1},
        "c": {"status": None},
        "d": {"status": "Idle", "model": "sonnet"},
    }[agent]


def _rows() -> list[dict[str, object]]:
    return fleet.build(
        [("a", "Ada"), ("b", "Bo"), ("c", "Cy"), ("d", "Di")],
        _info,
        lambda agent: 42,
        lambda agent: 3 if agent == "a" else 0,
        {"a": 100.0, "b": 50.0},
        {"a": 200.0},
    )


def test_each_agent_gets_a_status_and_a_stopped_agent_shows_no_live_numbers() -> None:
    rows = {r["id"]: r for r in _rows()}
    assert rows["a"]["status"] == "working" and rows["a"]["context_percent"] == 42
    assert rows["a"]["inbox"] == 3 and rows["a"]["model"] == "opus"
    assert rows["b"]["status"] == "crashed" and rows["b"]["crashed"] == 1
    assert rows["b"]["started"] is None and rows["b"]["context_percent"] is None
    assert rows["c"]["status"] == "stopped"
    assert rows["d"]["status"] == "idle"
    assert "secret-flag" not in json.dumps(rows)


def test_the_file_is_written_only_when_a_row_changes(tmp_path: Path) -> None:
    rows = _rows()
    assert fleet.write(tmp_path, rows, 1000.0)
    held = json.loads((tmp_path / fleet.NAME).read_text(encoding="utf-8"))
    assert held["format"] == fleet.FORMAT and len(held["agents"]) == 4
    assert not fleet.write(tmp_path, rows, 1010.0)
    # Output a few seconds later, in the same minute, is not a change.
    rows[0]["last_output"] = 210.0
    assert not fleet.write(tmp_path, rows, 1020.0)
    rows[2]["status"] = "idle"
    assert fleet.write(tmp_path, rows, 1030.0)


def test_the_fleet_call_lists_the_main_agent(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings())
    found = session.dispatch({"method": "fleet"})
    assert found["path"].endswith("fleet.json")
    assert found["agents"][0]["id"] == "hippoherman"
    assert found["agents"][0]["status"] == "stopped"


def test_traces_take_a_limit_for_the_replay(tmp_path: Path, monkeypatch: object) -> None:
    session = sidecar.Session(tmp_path, Settings())
    asked: list[int] = []

    def trace(agent: str, limit: int = 100) -> list[dict[str, object]]:
        asked.append(limit)
        return []

    monkeypatch.setattr(sidecar.cli_sessions, "tool_trace", trace)  # type: ignore[attr-defined]
    session.dispatch({"method": "terminal_traces", "agent": "a", "limit": 300})
    session.dispatch({"method": "terminal_traces", "agent": "a", "limit": 9999})
    assert asked == [300, 100]
