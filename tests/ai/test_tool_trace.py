import json
from pathlib import Path

from ai import cli_sessions


def test_tool_calls_come_back_newest_first_with_their_outcome(tmp_path: Path, monkeypatch) -> None:
    session = tmp_path / "s.jsonl"
    rows = [
        {
            "timestamp": "2026-11-12T10:00:00Z",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Bash",
                        "input": {"command": "ls notes"},
                    }
                ]
            },
        },
        {
            "timestamp": "2026-11-12T10:00:01Z",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]},
        },
        {
            "timestamp": "2026-11-12T10:01:00Z",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "rm x"}}
                ]
            },
        },
        {
            "timestamp": "2026-11-12T10:01:01Z",
            "message": {
                "content": [{"type": "tool_result", "tool_use_id": "t2", "is_error": True}]
            },
        },
        {
            "timestamp": "2026-11-12T10:02:00Z",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t3",
                        "name": "mcp__vault__read_note",
                        "input": {"path": "MAIN.md"},
                    }
                ]
            },
        },
        {"message": "not a dict"},
    ]
    session.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")
    monkeypatch.setattr(cli_sessions, "_transcript", lambda agent: session)
    trace = cli_sessions.tool_trace("ada")
    assert [(t["tool"], t["detail"], t["status"]) for t in trace] == [
        ("mcp__vault__read_note", "MAIN.md", "running"),
        ("Bash", "rm x", "failed"),
        ("Bash", "ls notes", "done"),
    ]
    assert trace[2]["at"] == "2026-11-12T10:00:00Z"
    assert cli_sessions.tool_trace("ada", limit=1)[0]["detail"] == "MAIN.md"


def test_an_agent_with_no_session_file_has_no_trace(monkeypatch) -> None:
    monkeypatch.setattr(cli_sessions, "_transcript", lambda agent: None)
    assert cli_sessions.tool_trace("ada") == []
