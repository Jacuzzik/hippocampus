"""Scheduled missions (K.15): a message sent to an agent on a schedule. Saved in data/storage/missions.json and run by
the same minute timer as the notes jobs, so there is one schedule list. A new mission starts switched off.

A schedule is either "every N minutes" (15 minutes to 7 days) or "on these weekdays at this time".
"""

import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core import safe_write

logger = logging.getLogger("hippocampus.missions")
MIN_MINUTES = 15
MAX_MINUTES = 7 * 24 * 60
CAP = 20
LABEL_MAX = 60
MESSAGE_MAX = 2000
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_lock = threading.Lock()


@dataclass(frozen=True)
class Mission:
    id: str
    label: str
    message: str
    agent: str
    every_minutes: int | None = None
    days: tuple[int, ...] = ()  # 0 is Monday
    at: str = ""  # "HH:MM", with days
    enabled: bool = False
    last_run: str | None = None


def check(row: dict[str, Any], mission_id: str) -> Mission:
    """A mission from the window's form, or ValueError saying in plain words what is wrong."""
    label = str(row.get("label") or "").strip()
    message = str(row.get("message") or "").strip()
    agent = str(row.get("agent") or "").strip()
    if not label or len(label) > LABEL_MAX:
        raise ValueError(f"The label must be 1 to {LABEL_MAX} characters.")
    if not message or len(message) > MESSAGE_MAX:
        raise ValueError(f"The message must be 1 to {MESSAGE_MAX} characters.")
    if not agent:
        raise ValueError("Pick the agent the mission is sent to.")
    every = row.get("every_minutes")
    days = row.get("days") or []
    at = str(row.get("at") or "")
    if every is not None:
        if not isinstance(every, int) or isinstance(every, bool):
            raise ValueError("The interval must be a whole number of minutes.")
        if not MIN_MINUTES <= every <= MAX_MINUTES:
            raise ValueError("The interval must be between 15 minutes and 7 days.")
        days, at = [], ""
    else:
        if (
            not isinstance(days, list)
            or not days
            or not all(isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 6 for d in days)
        ):
            raise ValueError("Pick at least one weekday, or an interval.")
        if not _TIME.match(at):
            raise ValueError('The time must look like "09:30".')
    return Mission(
        id=mission_id,
        label=label,
        message=message,
        agent=agent,
        every_minutes=every,
        days=tuple(sorted(set(days))),
        at=at,
        enabled=row.get("enabled") is True,
    )


def load(path: Path) -> list[Mission]:
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return [Mission(**{**row, "days": tuple(row.get("days") or ())}) for row in rows]
    except (ValueError, TypeError):
        logger.warning("missions file is unreadable; starting with none")
        return []


def save(path: Path, missions: list[Mission]) -> None:
    with _lock:
        safe_write.write_text(path, json.dumps([asdict(m) for m in missions], indent=2))


def upsert(missions: list[Mission], row: dict[str, Any]) -> list[Mission]:
    """Add a mission, or change the one whose id is given. Its last run is kept on a change."""
    given = str(row.get("id") or "")
    old = next((m for m in missions if m.id == given), None) if given else None
    if given and old is None:
        raise ValueError(f"no mission named {given}")
    if old is None and len(missions) >= CAP:
        raise ValueError(f"There are already {CAP} missions; remove one first.")
    used = {m.id for m in missions}
    new_id = given or next(
        f"mission-{n}" for n in range(1, CAP + len(used) + 2) if f"mission-{n}" not in used
    )
    mission = check(row, new_id)
    if old is not None:
        mission = replace(mission, last_run=old.last_run)
        return [mission if m.id == given else m for m in missions]
    return [*missions, mission]


def remove(missions: list[Mission], mission_id: object) -> list[Mission]:
    if not any(m.id == mission_id for m in missions):
        raise ValueError(f"no mission named {mission_id}")
    return [m for m in missions if m.id != mission_id]


def is_due(mission: Mission, now: datetime) -> bool:
    if not mission.enabled:
        return False
    last = datetime.fromisoformat(mission.last_run) if mission.last_run else None
    if mission.every_minutes is not None:
        return last is None or now - last >= timedelta(minutes=mission.every_minutes)
    if now.weekday() not in mission.days:
        return False
    hour, minute = (int(x) for x in mission.at.split(":"))
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= slot and (last is None or last < slot)


def run_due(
    missions: list[Mission], now: datetime, send: Callable[[Mission], None]
) -> tuple[list[Mission], list[str]]:
    """Send each due mission once. Returns the updated list and one log line per mission run."""
    out, lines = [], []
    for mission in missions:
        if is_due(mission, now):
            try:
                send(mission)
                lines.append(f"mission {mission.label}: sent to {mission.agent}")
            except (OSError, ValueError) as error:
                lines.append(f"mission {mission.label}: not sent ({error})")
            mission = replace(mission, last_run=now.isoformat(timespec="seconds"))
        out.append(mission)
    return out, lines
