"""8.12: after the daily compaction is typed and the agent is Idle again, it is pointed at its briefing again."""

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core import __main__ as sidecar
from core.settings import Settings


class FakeTerminals:
    def __init__(self) -> None:
        self.procs: dict[str, Any] = {"ada": object()}
        self.status = "Working"
        self.lines: list[str] = []
        self.resent: list[str] = []

    def info(self, agent: str) -> dict[str, Any]:
        return {"status": self.status}

    def send_line(self, agent: str, text: str) -> None:
        self.lines.append(text)

    def resend_briefing(self, agent: str) -> str:
        self.resent.append(agent)
        return "briefing.md"


def test_the_briefing_is_pointed_at_again_once_the_compaction_is_done(tmp_path: Path) -> None:
    # A long delivery interval, so the background loop does not run these steps too.
    session = sidecar.Session(tmp_path, Settings(delivery_seconds=60), emit=lambda e: None)
    fake = FakeTerminals()
    session.terminals = fake  # type: ignore[assignment]
    session.compact_day = datetime.now().date().isoformat()  # today's round already ran
    session.compact_waiting["ada"] = time.time() - 30  # the save prompt went out 30 s ago
    fake.status = "Idle"
    session._daily_compact()
    assert len(fake.lines) == 1 and "ada" in session.resend_after_compact  # compaction typed
    assert fake.resent == []  # too soon: the compaction has only just started
    session._daily_compact()
    assert fake.resent == []
    session.resend_after_compact["ada"] = time.time() - 30
    fake.status = "Working"  # still compacting
    session._daily_compact()
    assert fake.resent == []
    fake.status = "Idle"
    session._daily_compact()
    assert fake.resent == ["ada"] and not session.resend_after_compact
