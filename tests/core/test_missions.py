"""Scheduled missions (K.15): checks, the cap, when one is due, and a run that messages the agent."""

from datetime import datetime
from pathlib import Path

import pytest

from core import __main__ as sidecar
from core import inbox
from core import missions as m
from core.settings import Settings

ROW = {"label": "Morning check", "message": "Check the inbox", "agent": "ada", "every_minutes": 60}


def test_check_says_what_is_wrong_in_plain_words() -> None:
    with pytest.raises(ValueError, match="between 15 minutes and 7 days"):
        m.check({**ROW, "every_minutes": 5}, "x")
    with pytest.raises(ValueError, match="between 15 minutes and 7 days"):
        m.check({**ROW, "every_minutes": m.MAX_MINUTES + 1}, "x")
    with pytest.raises(ValueError, match="at least one weekday"):
        m.check({**ROW, "every_minutes": None, "days": [], "at": "09:00"}, "x")
    with pytest.raises(ValueError, match='look like "09:30"'):
        m.check({**ROW, "every_minutes": None, "days": [0], "at": "9am"}, "x")
    with pytest.raises(ValueError, match="label"):
        m.check({**ROW, "label": ""}, "x")
    weekly = m.check({**ROW, "every_minutes": None, "days": [4, 0, 0], "at": "09:30"}, "x")
    assert weekly.days == (0, 4) and not weekly.enabled


def test_a_new_mission_starts_off_and_the_cap_holds() -> None:
    missions: list[m.Mission] = []
    for _ in range(m.CAP):
        missions = m.upsert(missions, ROW)
    assert len({x.id for x in missions}) == m.CAP and not any(x.enabled for x in missions)
    with pytest.raises(ValueError, match="already 20 missions"):
        m.upsert(missions, ROW)
    changed = m.upsert(missions, {**ROW, "id": "mission-3", "enabled": True})
    assert next(x for x in changed if x.id == "mission-3").enabled
    assert len(m.remove(changed, "mission-3")) == m.CAP - 1


def test_due_by_interval_and_by_weekday_slot() -> None:
    now = datetime(2026, 11, 16, 10, 0)  # a Monday
    every = m.Mission("a", "l", "t", "ada", every_minutes=60, enabled=True)
    assert m.is_due(every, now)
    assert not m.is_due(m.Mission("a", "l", "t", "ada", every_minutes=60), now)  # off
    ran = m.Mission(
        "a", "l", "t", "ada", every_minutes=60, enabled=True, last_run="2026-11-16T09:30:00"
    )
    assert not m.is_due(ran, now)
    weekly = m.Mission("b", "l", "t", "ada", days=(0,), at="09:30", enabled=True)
    assert m.is_due(weekly, now) and not m.is_due(weekly, now.replace(hour=9))
    done = m.Mission(
        "b", "l", "t", "ada", days=(0,), at="09:30", enabled=True, last_run="2026-11-16T09:31:00"
    )
    assert not m.is_due(done, now)
    assert not m.is_due(weekly, datetime(2026, 11, 17, 10, 0))  # Tuesday


def test_a_switched_on_mission_messages_the_agent_once_and_is_logged(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session._agent_ids = lambda: {"hippoherman", "ada"}  # type: ignore[method-assign]
    added = session.dispatch({"method": "mission_save", "mission": ROW})["missions"]
    assert added[0]["enabled"] is False
    assert session.run_missions(datetime(2026, 11, 16, 10, 0)) == []  # off: nothing sent
    session.dispatch(
        {"method": "mission_save", "mission": {**ROW, "id": added[0]["id"], "enabled": True}}
    )
    assert session.run_missions(datetime(2026, 11, 16, 10, 0)) == [
        "mission Morning check: sent to ada"
    ]
    assert session.run_missions(datetime(2026, 11, 16, 10, 30)) == []  # not due again yet
    [(_, message)] = inbox.pending(session.hive_path, "ada")
    assert message["subject"] == "Morning check" and message["from"] == inbox.USER
    with pytest.raises(ValueError, match='No agent has the id "bob"'):
        session.dispatch({"method": "mission_save", "mission": {**ROW, "agent": "bob"}})
