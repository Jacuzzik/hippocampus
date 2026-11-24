"""7.31: usage statistics, local only. Counts read from this computer's own activity log; nothing is sent."""

from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from core import activity

STATEMENT = (
    "These numbers are counted on this computer from your own activity log. "
    "Nothing is collected, nothing is sent anywhere, and there is no account or identifier behind them."
)


def summarize(storage: Path, today: date | None = None, days: int = 14) -> dict[str, Any]:
    rows = activity.read(storage, None, 10**9)
    today = today or date.today()
    kinds = Counter(str(r.get("kind")) for r in rows)
    tools = Counter(str(r["tool"]) for r in rows if r.get("kind") == "tool" and r.get("tool"))
    agents = Counter(str(r["agent"]) for r in rows if r.get("agent"))
    approvals = [r for r in rows if r.get("kind") == "approval"]
    failed = sum(
        1 for r in rows if r.get("kind") == "tool" and r.get("status") in ("failed", "refused")
    )
    per_day = Counter(str(r.get("ts", ""))[:10] for r in rows)
    span = [(today - timedelta(days=n)).isoformat() for n in range(days - 1, -1, -1)]
    first = min((str(r.get("ts", ""))[:10] for r in rows if r.get("ts")), default=None)
    return {
        "statement": STATEMENT,
        "total": len(rows),
        "since": first,
        "kinds": [{"name": k, "count": n} for k, n in kinds.most_common()],
        "tools": [{"name": k, "count": n} for k, n in tools.most_common(8)],
        "agents": [{"name": k, "count": n} for k, n in agents.most_common(8)],
        "approvals": {
            "asked": len(approvals),
            "approved": sum(1 for r in approvals if r.get("approved")),
            "declined": sum(1 for r in approvals if not r.get("approved")),
        },
        "failed_tools": failed,
        "days": [{"day": d, "count": per_day.get(d, 0)} for d in span],
        "file": str(storage / "activity.jsonl"),
    }
