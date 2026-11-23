"""The calendar dashboard: the user's own events and the days scheduled jobs will run, by month.

Events live in data/storage/events.json on this computer. Nothing here reaches a network.
At an event's date and time (09:00 when it has no time) it goes to its agent as a message. The agent
reminds the user or does the work, then answers "done" or "refuse" with the event's id as "work";
that answer marks the event done or failed.
"""

import json
import logging
import re
import threading
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any

from core import safe_write
from core.jobs import Job

logger = logging.getLogger("hippocampus.calendar")
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
TITLE_MAX = 120
NOTE_MAX = 1000
EVENTS_MAX = 2000
MAIN_AGENT = "hippoherman"
DEFAULT_TIME = "09:00"
# An event missed by more than this (the app was closed) is marked missed, not sent late.
LATE_LIMIT = timedelta(hours=24)
STATUSES = ("scheduled", "sent", "done", "failed", "missed")
FIELDS = {"note": "", "agent": MAIN_AGENT, "status": "scheduled", "sent_at": "", "result": ""}
_lock = threading.Lock()
Event = dict[str, str]


def load(path: Path) -> list[Event]:
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        events = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            event = {key: str(row[key]) for key in ("id", "date", "time", "title")}
            event |= {key: str(row.get(key) or empty) for key, empty in FIELDS.items()}
            if event["status"] not in STATUSES:
                event["status"] = "scheduled"
            events.append(event)
        return events
    except (ValueError, KeyError, TypeError):
        logger.warning("events file is unreadable; starting with no events")
        return []


def _save(path: Path, events: list[Event]) -> None:
    safe_write.write_text(path, json.dumps(events, indent=2))


def add(
    path: Path,
    day: object,
    time: object,
    title: object,
    note: object = "",
    agent: object = MAIN_AGENT,
    agents: set[str] | None = None,
) -> Event:
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
    if note is not None and not isinstance(note, str):
        raise ValueError("The details must be text.")
    if len((note or "").strip()) > NOTE_MAX:
        raise ValueError(f"The details can be up to {NOTE_MAX} characters.")
    agent = agent or MAIN_AGENT
    if not isinstance(agent, str) or (agents is not None and agent not in agents):
        raise ValueError(f'No agent has the id "{agent}".')
    event = {
        "id": uuid.uuid4().hex[:12],
        "date": day,
        "time": time or "",
        "title": title.strip(),
        **FIELDS,
        "note": (note or "").strip(),
        "agent": agent,
    }
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


def set_status(path: Path, event_id: object, status: object) -> Event:
    """The user marks an event done or failed by hand, or sets it back to scheduled to send it again."""
    if status not in ("scheduled", "done", "failed"):
        raise ValueError("The status must be scheduled, done or failed.")
    with _lock:
        events = load(path)
        found = next((event for event in events if event["id"] == event_id), None)
        if found is None:
            raise ValueError("That event is not in the calendar.")
        found["status"] = str(status)
        if status == "scheduled":
            found["sent_at"] = found["result"] = ""
        else:
            found["result"] = found["result"] or "Marked by you."
        _save(path, events)
    return found


def due_at(event: Event, tz: tzinfo | None) -> datetime:
    """When the event goes to its agent: its date and time (09:00 without one), in the local zone."""
    return datetime.fromisoformat(f"{event['date']}T{event['time'] or DEFAULT_TIME}").replace(
        tzinfo=tz
    )


def send_due(path: Path, now: datetime, send: Callable[[Event], None]) -> list[str]:
    """Send each scheduled event whose time has come. Returns one log line per event handled."""
    lines: list[str] = []
    with _lock:
        events = load(path)
        changed = False
        for event in events:
            if event["status"] != "scheduled":
                continue
            when = due_at(event, now.tzinfo)
            if when > now:
                continue
            changed = True
            if now - when > LATE_LIMIT:
                event["status"] = "missed"
                event["result"] = "The app was closed at this time, so it was not sent."
                lines.append(f"calendar {event['title']}: missed")
                continue
            try:
                send(event)
            except (OSError, ValueError) as error:
                event["status"] = "failed"
                event["result"] = f"Could not reach {event['agent']}: {error}"
                lines.append(f"calendar {event['title']}: not sent ({error})")
                continue
            event["status"] = "sent"
            event["sent_at"] = now.isoformat(timespec="seconds")
            lines.append(f"calendar {event['title']}: sent to {event['agent']}")
        if changed:
            _save(path, events)
    return lines


def settle(path: Path, messages: list[dict[str, Any]]) -> list[str]:
    """Mark each sent event done or failed from its agent's answer: a "done" or "refuse" with its id as work."""
    answers: dict[tuple[str, str], dict[str, Any]] = {}
    for message in messages:  # newest first, so the first answer seen is the latest
        if message.get("act") in ("done", "refuse") and message.get("work"):
            answers.setdefault((str(message.get("from")), str(message["work"])), message)
    lines: list[str] = []
    with _lock:
        events = load(path)
        changed = False
        for event in events:
            answer = answers.get((event["agent"], event["id"]))
            if event["status"] != "sent" or answer is None:
                continue
            event["status"] = "done" if answer["act"] == "done" else "failed"
            text = str(answer.get("body") or answer.get("subject") or "").strip()
            event["result"] = text[:300]
            changed = True
            lines.append(f"calendar {event['title']}: {event['status']}")
        if changed:
            _save(path, events)
    return lines


def upcoming(path: Path, now: datetime, count: int = 4) -> list[Event]:
    """The next events still to come or still being worked on, soonest first."""
    rows = [
        event
        for event in load(path)
        if event["status"] == "sent"
        or (event["status"] == "scheduled" and due_at(event, now.tzinfo) >= now)
    ]
    rows.sort(key=lambda event: (event["date"], event["time"] or DEFAULT_TIME, event["title"]))
    return rows[:count]


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
    # A week at either edge of the month is included, so a week view that crosses months is whole.
    start, end = (first - timedelta(days=7)).isoformat(), (last + timedelta(days=7)).isoformat()
    events = sorted(
        (event for event in load(path) if start <= event["date"] <= end),
        key=lambda event: (event["date"], event["time"], event["title"]),
    )
    runs = [
        {"date": day, "name": job.name}
        for job in jobs
        for day in job_days(job, first - timedelta(days=7), last + timedelta(days=7), today)
    ]
    return {
        "month": month,
        "first_weekday": first.weekday(),  # 0 is Monday
        "days": last.day,
        "today": today.isoformat(),
        "events": events,
        "job_runs": sorted(runs, key=lambda run: (run["date"], run["name"])),
    }
