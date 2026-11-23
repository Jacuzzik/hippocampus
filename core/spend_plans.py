"""The Money and spend dashboard: what the user pays for AI each month, from their own numbers.

The user enters each plan (a monthly subscription) and, for pay-as-you-go use, a price per million
tokens. Token counts come from provider_usage, so the cost is the user's price times the real count.
No price is guessed. The plans live in data/storage/spend_plans.json.
"""

import calendar
import json
import threading
from datetime import date
from pathlib import Path
from typing import Any

from core import safe_write

PLANS_MAX = 40
NAME_MAX = 60
MONEY_MAX = 1_000_000.0
CURRENCIES = ("USD", "EUR", "GBP", "AED", "INR", "SAR", "CAD", "AUD", "JPY")
_lock = threading.Lock()


def _money(value: object, name: str) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= MONEY_MAX:
        raise ValueError(f'"{name}" must be a number from 0 to {MONEY_MAX:,.0f}.')
    return round(float(value), 4)


def check(raw: object) -> dict[str, Any]:
    """The plans as saved, or ValueError with a plain reason."""
    if not isinstance(raw, dict):
        raise ValueError("The plans must be an object.")
    currency = str(raw.get("currency") or "USD")
    if currency not in CURRENCIES:
        raise ValueError(f"The currency must be one of: {', '.join(CURRENCIES)}.")
    rows = raw.get("plans") or []
    if not isinstance(rows, list) or len(rows) > PLANS_MAX:
        raise ValueError(f"Up to {PLANS_MAX} plans can be kept.")
    plans = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each plan must be an object.")
        name = str(row.get("name") or "").strip()
        if not name or len(name) > NAME_MAX:
            raise ValueError(f"Each plan needs a name of up to {NAME_MAX} characters.")
        plans.append(
            {
                "name": name,
                "provider": str(row.get("provider") or ""),
                "monthly": _money(row.get("monthly"), "monthly"),
                "per_million": _money(row.get("per_million"), "per_million"),
            }
        )
    return {"currency": currency, "plans": plans}


def load(path: Path) -> dict[str, Any]:
    try:
        return check(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {"currency": "USD", "plans": []}


def save(path: Path, raw: object) -> dict[str, Any]:
    plans = check(raw)
    with _lock:
        safe_write.write_text(path, json.dumps(plans, indent=2))
    return plans


def report(plans: dict[str, Any], usage: dict[str, Any], today: date) -> dict[str, Any]:
    """This month's cost per plan, the total, and a straight-line guess for the whole month."""
    by_provider = {p["id"]: p for p in usage.get("providers", [])}
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    rows = []
    daily = [0.0] * int(usage.get("days") or 0)
    for plan in plans["plans"]:
        found = by_provider.get(plan["provider"], {})
        tokens = int(found.get("month") or 0) if plan["per_million"] else 0
        metered = tokens / 1_000_000 * plan["per_million"]
        if plan["per_million"]:
            for i, day_tokens in enumerate(found.get("days") or []):
                if i < len(daily):
                    daily[i] += day_tokens / 1_000_000 * plan["per_million"]
        rows.append(
            {
                **plan,
                "provider_name": found.get("name", ""),
                "tokens": tokens,
                "metered": round(metered, 2),
                "total": round(plan["monthly"] + metered, 2),
            }
        )
    fixed = sum(row["monthly"] for row in rows)
    metered = sum(row["metered"] for row in rows)
    return {
        "currency": plans["currency"],
        "rows": rows,
        "fixed": round(fixed, 2),
        "metered": round(metered, 2),
        "total": round(fixed + metered, 2),
        # Pay-as-you-go so far, spread over the whole month, plus the plans.
        "projected": round(fixed + metered / today.day * days_in_month, 2),
        "day": today.day,
        "days_in_month": days_in_month,
        "daily": [round(value, 2) for value in daily],
    }
