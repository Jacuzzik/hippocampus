"""The circuit breaker: a loop, a run of failures, a full context or repeated crashes, each steered once."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import core.__main__ as sidecar
from core import breaker
from core.settings import Settings

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def _calls(n: int, status: str = "done", detail: str = "ls") -> list[dict[str, Any]]:
    return [{"tool": "Bash", "detail": detail, "status": status} for _ in range(n)]


def test_a_quiet_agent_is_healthy() -> None:
    found = breaker.assess("a", _calls(2) + _calls(3, detail="pwd"), 30, [], NOW)
    assert found["level"] == "healthy" and found["reasons"] == []


def test_the_same_call_warns_at_three_and_trips_at_five() -> None:
    assert breaker.assess("a", _calls(3), None, [], NOW)["level"] == "warn"
    found = breaker.assess("a", _calls(5), None, [], NOW)
    assert found["level"] == "tripped"
    line = breaker.steer_text(found["reasons"][0], "/compact")
    assert line is not None and "5 times in a row" in line


def test_a_run_of_failures_trips() -> None:
    trace = [{"tool": "Bash", "detail": f"try {i}", "status": "failed"} for i in range(6)]
    found = breaker.assess("a", trace + _calls(2, detail="x"), None, [], NOW)
    assert [r["kind"] for r in found["reasons"]] == ["failing"]
    assert found["level"] == "tripped"


def test_a_full_context_is_steered_with_the_compact_prompt() -> None:
    assert breaker.assess("a", [], 85, [], NOW)["level"] == "warn"
    found = breaker.assess("a", [], 95, [], NOW)
    assert breaker.steer_text(found["reasons"][0], "/compact keep it") == "/compact keep it"


def test_three_crashes_in_15_minutes_trip_but_are_not_typed_to_the_agent() -> None:
    rows = [
        {"source": "agent a", "at": (NOW - timedelta(minutes=m)).isoformat()} for m in (1, 5, 9)
    ] + [{"source": "agent b", "at": NOW.isoformat()}]
    found = breaker.assess("a", [], None, rows, NOW)
    assert found["level"] == "tripped"
    assert breaker.steer_text(found["reasons"][0], "/compact") is None
    old = [{"source": "agent a", "at": (NOW - timedelta(hours=1)).isoformat()}] * 3
    assert breaker.assess("a", [], None, old, NOW)["level"] == "healthy"


def test_a_tripped_running_agent_is_steered_once_per_cooldown(
    tmp_path: Path, monkeypatch: Any
) -> None:
    session = sidecar.Session(tmp_path, Settings())
    typed: list[tuple[str, str]] = []
    monkeypatch.setattr(session.terminals, "send_line", lambda a, t: typed.append((a, t)))
    monkeypatch.setattr(sidecar.cli_sessions, "tool_trace", lambda agent, limit: _calls(6))
    row = {"id": "hippoherman", "status": "working", "context_percent": 10}
    session._check_breakers([row])
    session._check_breakers([row])
    assert len(typed) == 1 and "Circuit breaker" in typed[0][1]
    state = session.dispatch({"method": "breakers"})["breakers"]
    assert state[0]["level"] == "tripped"
    stopped = {"id": "hippoherman", "status": "stopped", "context_percent": None}
    session.breaker_sent.clear()
    session._check_breakers([stopped])
    assert len(typed) == 1
