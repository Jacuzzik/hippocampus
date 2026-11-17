"""The calendar dashboard: the user's own events and the days scheduled jobs will run, by month.

Events live in data/storage/events.json on this computer. Nothing here reaches a network.
"""

import json
import logging
import re
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from core import safe_write
from core.jobs import Job

logger = logging.getLogger("hippocampus.calendar")
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
TITLE_MAX = 120
EVENTS_MAX = 2000
_lock = threading.Lock()
Event = dict[str, str]


def load(path: Path) -> list[Event]:
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return [
            {key: str(row[key]) for key in ("id", "date", "time", "title")}
            for row in rows
            if isinstance(row, dict)
        ]
    except (ValueError, KeyError, TypeError):
        logger.warning("events file is unreadable; starting with no events")
        return []


def _save(path: Path, events: list[Event]) -> None:
    safe_write.write_text(path, json.dumps(events, indent=2))


def add(path: Path, day: object, time: object, title: object) -> Event:
    if not isinstance(day, str):
        raise ValueError("The date must be written as YYYY-MM-DD.")
    try:
        date.fromisoformat(day)
    except ValueError as error:
        raise ValueError("The date must be written as YYYY-MM-DD.") from error
    if time not in (None, "") and not (isinstance(time, str) and TIME.match(time)):
        raise ValueError("The time must be written as HH:MM, or left empty.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("An event needs a title.")
    if len(title.strip()) > TITLE_MAX:
        raise ValueError(f"A title can be up to {TITLE_MAX} characters.")
    event = {"id": uuid.uuid4().hex[:12], "date": day, "time": time or "", "title": title.strip()}
    with _lock:
        events = load(path)
        if len(events) >= EVENTS_MAX:
            raise ValueError(f"The calendar holds up to {EVENTS_MAX} events. Remove some first.")
        _save(path, [*events, event])
    return event


def remove(path: Path, event_id: object) -> None:
    with _lock:
        events = load(path)
        kept = [event for event in events if event["id"] != event_id]
        if len(kept) == len(events):
            raise ValueError("That event is not in the calendar.")
        _save(path, kept)


def _month_days(month: str) -> tuple[date, date]:
    first = date.fromisoformat(f"{month}-01")
    after = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first, after - timedelta(days=1)


def job_days(job: Job, first: date, last: date, today: date) -> list[str]:
    """The days in [first, last] an enabled job is due to run, from today on. A job never run is due today."""
    if not job.enabled:
        return []
    due = today if job.last_run is None else datetime.fromisoformat(job.last_run).date()
    if job.last_run is not None:
        due += timedelta(days=job.every_days)
    due = max(due, today)  # an overdue job runs at the next check, which is today
    days = []
    while due <= last:
        if due >= first:
            days.append(due.isoformat())
        due += timedelta(days=job.every_days)
    return days


def month_view(path: Path, jobs: list[Job], month: object, today: date) -> dict[str, Any]:
    if not isinstance(month, str) or not MONTH.match(month):
        raise ValueError("The month must be written as YYYY-MM.")
    first, last = _month_days(month)
    events = sorted(
        (event for event in load(path) if event["date"].startswith(month)),
        key=lambda event: (event["date"], event["time"], event["title"]),
    )
    runs = [
        {"date": day, "name": job.name} for job in jobs for day in job_days(job, first, last, today)
    ]
    return {
        "month": month,
        "first_weekday": first.weekday(),  # 0 is Monday
        "days": last.day,
        "today": today.isoformat(),
        "events": events,
        "job_runs": sorted(runs, key=lambda run: (run["date"], run["name"])),
    }
