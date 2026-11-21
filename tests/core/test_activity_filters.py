"""7.14: the activity log can be read for one agent and for a date range."""

import json
from pathlib import Path

import pytest

import core.__main__ as sidecar
from core.settings import Settings


def _session(tmp_path: Path) -> sidecar.Session:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    rows = [
        {"ts": "2026-11-01T09:00:00+00:00", "kind": "tool", "agent": "ada", "name": "a"},
        {"ts": "2026-11-10T09:00:00+00:00", "kind": "tool", "agent": "bob", "name": "b"},
        {"ts": "2026-11-20T09:00:00+00:00", "kind": "error", "agent": "ada", "name": "c"},
    ]
    (tmp_path / "activity.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return session


def _names(session: sidecar.Session, **request: str) -> list[str]:
    return [r["name"] for r in session.dispatch({"method": "activity", **request})["rows"]]


def test_filter_by_agent_and_by_date_range(tmp_path: Path) -> None:
    session = _session(tmp_path)
    assert _names(session) == ["c", "b", "a"]
    assert _names(session, agent="ada") == ["c", "a"]
    assert _names(session, since="2026-11-05") == ["c", "b"]
    assert _names(session, until="2026-11-10") == ["b", "a"]
    assert _names(session, since="2026-11-10", until="2026-11-10", agent="bob") == ["b"]


def test_a_bad_date_is_refused_with_a_plain_sentence(tmp_path: Path) -> None:
    session = _session(tmp_path)
    with pytest.raises(ValueError, match="must be a date"):
        session.dispatch({"method": "activity", "since": "yesterday"})
