"""The calendar dashboard keeps the user's events and shows the days scheduled jobs will run."""

from datetime import date
from pathlib import Path

import pytest

from core import calendar_board
from core.jobs import Job


def test_an_event_is_added_listed_in_its_month_and_removed(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    late = calendar_board.add(path, "2026-11-20", "15:30", "  Dentist ")
    early = calendar_board.add(path, "2026-11-20", "", "Pay rent")
    calendar_board.add(path, "2026-12-01", "09:00", "Next month")
    view = calendar_board.month_view(path, [], "2026-11", date(2026, 11, 17))
    assert [event["title"] for event in view["events"]] == ["Pay rent", "Dentist"]
    assert (view["days"], view["first_weekday"], view["today"]) == (30, 6, "2026-11-17")
    calendar_board.remove(path, early["id"])
    view = calendar_board.month_view(path, [], "2026-11", date(2026, 11, 17))
    assert [event["id"] for event in view["events"]] == [late["id"]]
    with pytest.raises(ValueError, match="not in the calendar"):
        calendar_board.remove(path, early["id"])


@pytest.mark.parametrize(
    ("day", "time", "title", "reason"),
    [
        ("20-11-2026", "", "x", "YYYY-MM-DD"),
        ("2026-02-30", "", "x", "YYYY-MM-DD"),
        (None, "", "x", "YYYY-MM-DD"),
        ("2026-11-20", "25:00", "x", "HH:MM"),
        ("2026-11-20", "9am", "x", "HH:MM"),
        ("2026-11-20", "", "   ", "needs a title"),
        ("2026-11-20", "", "x" * 121, "up to 120"),
    ],
)
def test_a_bad_event_is_refused_with_the_reason(
    tmp_path: Path, day: object, time: object, title: object, reason: str
) -> None:
    with pytest.raises(ValueError, match=reason):
        calendar_board.add(tmp_path / "events.json", day, time, title)
    assert not (tmp_path / "events.json").exists()


def test_job_days_repeat_from_the_last_run_and_never_fall_in_the_past() -> None:
    first, last, today = date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 17)
    weekly = Job("a", "Weekly link check", "link_check", 7, True, "2026-11-12T09:00:00+00:00")
    assert calendar_board.job_days(weekly, first, last, today) == ["2026-11-19", "2026-11-26"]
    never_run = Job("a", "Weekly link check", "link_check", 7, True, None)
    assert calendar_board.job_days(never_run, first, last, today) == ["2026-11-17", "2026-11-24"]
    overdue = Job("a", "Weekly link check", "link_check", 7, True, "2026-10-01T09:00:00+00:00")
    assert calendar_board.job_days(overdue, first, last, today)[0] == "2026-11-17"
    off = Job("a", "Weekly link check", "link_check", 7, False, None)
    assert calendar_board.job_days(off, first, last, today) == []


def test_the_month_must_be_year_dash_month_and_a_broken_file_reads_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    for bad in ("2026-13", "2026-1", "nov", None):
        with pytest.raises(ValueError, match="YYYY-MM"):
            calendar_board.month_view(path, [], bad, date(2026, 11, 17))
    path.write_text("not json", encoding="utf-8")
    assert calendar_board.month_view(path, [], "2026-11", date(2026, 11, 17))["events"] == []
    job = Job("a", "Weekly link check", "link_check", 7, True, None)
    view = calendar_board.month_view(path, [job], "2026-12", date(2026, 11, 17))
    assert view["job_runs"][0] == {"date": "2026-12-01", "name": "Weekly link check"}
    assert len(view["job_runs"]) == 5
