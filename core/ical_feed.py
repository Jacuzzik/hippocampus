"""Calendars (D.07): events from a calendar's private iCal address, shown in the daily brief and on the
Calendar board.

Google Calendar gives each calendar a "Secret address in iCal format" (Settings, the calendar,
Integrate calendar); Outlook and Apple iCloud give the same kind of link. The link is a password in
itself, so it is kept in the system keychain, never in a file. Reading it is one GET; nothing is sent.
Weekly and daily repeats are expanded; other repeat rules show the first time only.
"""

import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.apps import http_get

Get = Callable[[str, dict[str, str]], tuple[int, bytes]]
DAYS_AHEAD = 14
EVENTS_MAX = 200
WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def check_link(url: object) -> str:
    link = str(url or "").strip()
    if link.startswith("webcal://"):
        link = "https://" + link[len("webcal://") :]
    if not re.match(r"^https://[^\s/]+/\S+$", link):
        raise ValueError(
            "Paste the calendar's secret iCal address (it starts with https:// or webcal://)."
        )
    return link


def _lines(text: str) -> list[str]:
    # A line that starts with a space or a tab continues the one before it (RFC 5545 folding).
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and out:
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


def _when(name: str, value: str, local: tzinfo | None) -> tuple[datetime, bool]:
    """The start as a local datetime, and whether it is an all-day event."""
    if "VALUE=DATE" in name and "VALUE=DATE-TIME" not in name or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=local), True
    found = re.search(r"TZID=([^;:]+)", name)
    moment = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    elif found:
        try:
            moment = moment.replace(tzinfo=ZoneInfo(found.group(1)))
        except (ZoneInfoNotFoundError, ValueError):
            moment = moment.replace(tzinfo=local)
    else:
        moment = moment.replace(tzinfo=local)
    return moment.astimezone(local), False


def _unescape(text: str) -> str:
    return (
        text.replace("\\n", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def parse(
    text: str, today: date, local: tzinfo | None, days: int = DAYS_AHEAD
) -> list[dict[str, str]]:
    """The events from today to `days` ahead, soonest first, as {date, time, title, status}."""
    last = today + timedelta(days=days)
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in _lines(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            events += _expand(current, today, last, local)
            current = None
        elif current is not None and ":" in line:
            name, _, value = line.partition(":")
            key = name.split(";")[0].upper()
            if key in ("DTSTART", "SUMMARY", "RRULE", "STATUS"):
                current[key] = value
                if key == "DTSTART":
                    current["DTSTART_NAME"] = name
    events.sort(key=lambda e: (e["date"], e["time"] or "00:00", e["title"]))
    return events[:EVENTS_MAX]


def _expand(
    raw: dict[str, str], first: date, last: date, local: tzinfo | None
) -> list[dict[str, str]]:
    if "DTSTART" not in raw or raw.get("STATUS", "").upper() == "CANCELLED":
        return []
    try:
        start, all_day = _when(raw.get("DTSTART_NAME", "DTSTART"), raw["DTSTART"], local)
    except ValueError:
        return []
    title = _unescape(raw.get("SUMMARY", "")) or "(no title)"
    starts = [start]
    rule = dict(p.split("=", 1) for p in raw.get("RRULE", "").split(";") if "=" in p)
    freq = rule.get("FREQ", "")
    if freq in ("DAILY", "WEEKLY"):
        step = timedelta(days=1 if freq == "DAILY" else 7) * max(
            1, int(rule.get("INTERVAL", "1") or 1)
        )
        until = last
        if rule.get("UNTIL"):
            try:
                until = min(last, datetime.strptime(rule["UNTIL"][:8], "%Y%m%d").date())
            except ValueError:
                pass
        count = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
        days = [
            WEEKDAYS.index(d[-2:]) for d in rule.get("BYDAY", "").split(",") if d[-2:] in WEEKDAYS
        ]
        starts = []
        moment, made = start, 0
        while moment.date() <= until and (count is None or made < count):
            if freq == "WEEKLY" and days:
                week = moment - timedelta(days=moment.weekday())
                for d in sorted(days):
                    hit = week + timedelta(days=d)
                    if hit >= start and hit.date() <= until and (count is None or made < count):
                        starts.append(hit)
                        made += 1
            else:
                starts.append(moment)
                made += 1
            moment += step
    return [
        {
            "date": s.date().isoformat(),
            "time": "" if all_day else s.strftime("%H:%M"),
            "title": title,
            "status": "calendar",
        }
        for s in starts
        if first <= s.date() <= last
    ]


def read(link: str, today: date, local: tzinfo | None, get: Get = http_get) -> list[dict[str, str]]:
    status, body = get(link, {"Accept": "text/calendar", "User-Agent": "hippocampus"})
    if status in (301, 302, 303, 307, 308):
        raise ValueError("The calendar address redirects. Paste the secret iCal address itself.")
    if status != 200:
        raise ValueError(
            f"The calendar answered {status}. Check that the secret address is still valid."
        )
    text = body.decode("utf-8", "replace")
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("That address did not give a calendar. Paste the secret iCal address.")
    return parse(text, today, local)
