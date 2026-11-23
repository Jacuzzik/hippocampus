"""The daily brief note: made from what the app holds, written into the vault, rewritten the same day."""

from datetime import date
from pathlib import Path

import core.__main__ as sidecar
from core import daily_brief, jobs
from core.settings import Settings


def test_the_brief_lists_today_tasks_agents_messages_and_yesterday() -> None:
    text = daily_brief.compose(
        date(2026, 11, 23),
        [
            {"date": "2026-11-23", "time": "10:00", "title": "Standup", "status": "scheduled"},
            {"date": "2026-11-25", "time": "", "title": "Release", "status": "scheduled"},
        ],
        [
            {"id": "K-1", "title": "Ship it", "status": "doing", "assignee": "ada"},
            {"id": "K-2", "title": "Pick a name", "status": "blocked", "waiting": True},
        ],
        [{"name": "Hippoherman", "status": "idle", "inbox": 2, "breaker": "warn"}],
        4,
        [{"kind": "error", "text": "boom"}, {"kind": "setting", "text": "x"}],
    )
    assert "- 10:00 Standup (scheduled)" in text
    assert "- Next: 2026-11-25 Release" in text
    assert "1 doing, 1 blocked." in text
    assert "Waiting on you: K-2 Pick a name" in text
    assert "Hippoherman is idle: 2 waiting in its inbox, circuit breaker warn." in text
    assert "4 unread for you" in text
    assert "1 error, 1 setting." in text and "Error: boom" in text


def test_the_job_is_listed_and_off_by_default(tmp_path: Path) -> None:
    found = {job.id: job for job in jobs.load(tmp_path / "jobs.json")}
    assert found["daily-brief"].kind == "daily_brief"
    assert found["daily-brief"].enabled is False


def test_running_the_job_writes_the_note_and_rewrites_it_the_same_day(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# A\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "s", Settings(vault=vault))
    session.dispatch({"method": "open", "vault": str(vault)})
    for _ in range(2):
        answer = session.dispatch({"method": "run_job", "id": "daily-brief", "approve": True})
        assert answer["result"].startswith("Daily brief note: wrote the daily brief")
    notes = list((vault / daily_brief.FOLDER).glob("*.md"))
    assert len(notes) == 1
    assert notes[0].read_text(encoding="utf-8").startswith("# Daily brief ")
