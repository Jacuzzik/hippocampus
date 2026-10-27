"""Token budgets: caps per day, week and month, for the whole app and for the assistant.

Usage is one JSON line per model reply in storage/usage.jsonl. Windows start 5 hours ago (a
rolling window), at local midnight, Monday, or the 1st of the month.
"""

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from core.settings import CAP_WINDOWS, Caps

logger = logging.getLogger("hippocampus.budget")


@dataclass(frozen=True)
class Overrun:
    scope: str
    window: str
    used: int
    cap: int

    def as_dict(self) -> dict[str, object]:
        return {"scope": self.scope, "window": self.window, "used": self.used, "cap": self.cap}


def window_start(window: str, now: datetime) -> datetime:
    if window == "five_hour":
        return now - timedelta(hours=5)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "daily":
        return midnight
    if window == "weekly":
        return midnight - timedelta(days=midnight.weekday())
    return midnight.replace(day=1)


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def add(self, agent: str, tokens: int, now: datetime | None = None) -> None:
        if tokens <= 0:
            return
        when = (now or datetime.now().astimezone()).isoformat()
        line = json.dumps({"ts": when, "agent": agent, "tokens": tokens})
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as out:
                out.write(line + "\n")

    def used(self, window: str, now: datetime, agent: str | None = None) -> int:
        """Tokens used in the current window. `agent` None counts every agent (the app)."""
        start = window_start(window, now)
        total = 0
        with self._lock:
            lines = (
                self.path.read_text(encoding="utf-8").splitlines() if self.path.is_file() else []
            )
        for line in lines:
            try:
                row = json.loads(line)
                when = datetime.fromisoformat(row["ts"])
            except (ValueError, KeyError, TypeError):
                logger.warning("skipping a malformed usage line")
                continue
            if when >= start and (agent is None or row.get("agent") == agent):
                total += int(row.get("tokens", 0))
        return total

    def first_overrun(
        self, scopes: dict[str, tuple[Caps, str | None]], now: datetime | None = None
    ) -> Overrun | None:
        """The first cap already reached, checked scope by scope. None when every cap has room."""
        when = now or datetime.now().astimezone()
        for scope, (caps, agent) in scopes.items():
            for window in CAP_WINDOWS:
                cap = getattr(caps, window)
                if cap <= 0:
                    continue
                used = self.used(window, when, agent)
                if used >= cap:
                    return Overrun(scope, window, used, cap)
        return None
