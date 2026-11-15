"""The ledger says how many tokens each agent used in a window."""

from datetime import datetime, timedelta
from pathlib import Path

from core.budget import Ledger


def test_by_agent_sums_today_and_orders_biggest_first(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "usage.jsonl")
    now = datetime(2026, 11, 15, 12, 0).astimezone()
    ledger.add("kevin", 100, now)
    ledger.add("assistant", 700, now)
    ledger.add("kevin", 50, now)
    ledger.add("pam", 900, now - timedelta(days=2))  # before today: not counted
    assert list(ledger.by_agent("daily", now).items()) == [("assistant", 700), ("kevin", 150)]


def test_by_agent_skips_broken_lines(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    ledger = Ledger(path)
    now = datetime(2026, 11, 15, 12, 0).astimezone()
    ledger.add("kevin", 10, now)
    with path.open("a", encoding="utf-8") as out:
        out.write("not json\n")
    assert ledger.by_agent("daily", now) == {"kevin": 10}
