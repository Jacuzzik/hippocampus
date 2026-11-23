"""The Money and spend dashboard: what the user pays for AI each month, from their own numbers.

The user enters each plan (a monthly subscription) and, for pay-as-you-go use, a price per million
tokens. Token counts come from provider_usage, so the cost is the user's price times the real count.
No price is guessed. The plans live in data/storage/spend_plans.json.

Subscriptions (Apple, Google Play or anything else) are kept beside the plans. Apple offers no way
for an app to read a person's subscriptions, so the user enters each one; "Manage" opens Apple's
own subscriptions page, where cancelling and resubscribing happen. A cancelled subscription whose
renewal date has passed counts as expired.

Wallets are the balances the user holds with a payment service (Tebex, PayPal, Stripe, a bank or a
crypto wallet). None of these offers a read-only balance Hippocampus can use with a shop key (Tebex
has no wallet API at all), so the user enters each balance and its date; "Open" goes to the
service's own wallet page.
"""

import calendar
import json
import re
import threading
from datetime import date
from pathlib import Path
from typing import Any

from core import safe_write

PLANS_MAX = 40
NAME_MAX = 60
MONEY_MAX = 1_000_000.0
CURRENCIES = ("USD", "EUR", "GBP", "AED", "INR", "SAR", "CAD", "AUD", "JPY")
SUBS_MAX = 60
STORES = {
    "apple": "https://apps.apple.com/account/subscriptions",
    "google": "https://play.google.com/store/account/subscriptions",
    "other": "",
}
PERIODS = ("month", "year", "week")
STATUSES = ("active", "cancelled", "expired")
WALLETS_MAX = 30
WALLETS = {
    "tebex": "https://creator.tebex.io/",
    "paypal": "https://www.paypal.com/myaccount/summary",
    "stripe": "https://dashboard.stripe.com/balance/overview",
    "builtbybit": "https://builtbybit.com/",
    "bank": "",
    "crypto": "",
    "other": "",
}
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_lock = threading.Lock()


def _link(value: object) -> str:
    link = str(value or "").strip()
    if link and (
        not link.startswith("https://") or len(link) > 500 or any(c in link for c in " \r\n")
    ):
        raise ValueError("A link must be an https address.")
    return link


def _subs(rows: object) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) > SUBS_MAX:
        raise ValueError(f"Up to {SUBS_MAX} subscriptions can be kept.")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each subscription must be an object.")
        name = str(row.get("name") or "").strip()
        if not name or len(name) > NAME_MAX:
            raise ValueError(f"Each subscription needs a name of up to {NAME_MAX} characters.")
        store = str(row.get("store") or "apple")
        period = str(row.get("period") or "month")
        status = str(row.get("status") or "active")
        renews = str(row.get("renews") or "")
        if store not in STORES or period not in PERIODS or status not in STATUSES:
            raise ValueError("A subscription's store, period or status is not one of the choices.")
        if renews and not DAY.match(renews):
            raise ValueError("A renewal date must look like 2026-12-31.")
        out.append(
            {
                "name": name,
                "store": store,
                "price": _money(row.get("price"), "price"),
                "period": period,
                "renews": renews,
                "status": status,
                "link": _link(row.get("link")),
            }
        )
    return out


def _wallets(rows: object) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) > WALLETS_MAX:
        raise ValueError(f"Up to {WALLETS_MAX} wallets can be kept.")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each wallet must be an object.")
        name = str(row.get("name") or "").strip()
        if not name or len(name) > NAME_MAX:
            raise ValueError(f"Each wallet needs a name of up to {NAME_MAX} characters.")
        kind = str(row.get("kind") or "other")
        currency = str(row.get("currency") or "USD")
        updated = str(row.get("updated") or "")
        if kind not in WALLETS or currency not in CURRENCIES:
            raise ValueError("A wallet's service or currency is not one of the choices.")
        if updated and not DAY.match(updated):
            raise ValueError("A balance date must look like 2026-12-31.")
        out.append(
            {
                "name": name,
                "kind": kind,
                "balance": _money(row.get("balance"), "balance"),
                "currency": currency,
                "updated": updated,
                "link": _link(row.get("link")),
            }
        )
    return out


def wallet_rows(wallets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each wallet with the page that opens it, largest balance first."""
    rows = [{**w, "open": w["link"] or WALLETS[w["kind"]]} for w in wallets]
    rows.sort(key=lambda row: (-row["balance"], row["name"].lower()))
    return rows


def wallet_totals(wallets: list[dict[str, Any]]) -> dict[str, float]:
    """The balances added up per currency; different currencies are never mixed."""
    totals: dict[str, float] = {}
    for w in wallets:
        totals[w["currency"]] = round(totals.get(w["currency"], 0.0) + w["balance"], 2)
    return totals


def monthly(sub: dict[str, Any]) -> float:
    """A subscription's price as a monthly amount."""
    per = {"month": 1.0, "year": 1 / 12, "week": 52 / 12}[sub["period"]]
    return round(sub["price"] * per, 2)


def sub_rows(subs: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """Each subscription with its state for today and the page that manages or renews it."""
    rows = []
    for sub in subs:
        state = sub["status"]
        if state == "cancelled" and sub["renews"] and sub["renews"] < today.isoformat():
            state = "expired"
        rows.append(
            {
                **sub,
                "state": state,
                "active": state == "active",
                "monthly": monthly(sub),
                "manage": STORES[sub["store"]],
                "resubscribe": sub["link"] or STORES[sub["store"]],
            }
        )
    rows.sort(key=lambda row: (not row["active"], row["renews"] or "9999", row["name"].lower()))
    return rows


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
    return {
        "currency": currency,
        "plans": plans,
        "subs": _subs(raw.get("subs") or []),
        "wallets": _wallets(raw.get("wallets") or []),
    }


def load(path: Path) -> dict[str, Any]:
    try:
        return check(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {"currency": "USD", "plans": [], "subs": [], "wallets": []}


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
    subs = sub_rows(plans.get("subs", []), today)
    fixed = sum(row["monthly"] for row in rows) + sum(s["monthly"] for s in subs if s["active"])
    metered = sum(row["metered"] for row in rows)
    return {
        "currency": plans["currency"],
        "rows": rows,
        "subs": subs,
        "wallets": wallet_rows(plans.get("wallets", [])),
        "wallet_totals": wallet_totals(plans.get("wallets", [])),
        "subs_monthly": round(sum(s["monthly"] for s in subs if s["active"]), 2),
        "fixed": round(fixed, 2),
        "metered": round(metered, 2),
        "total": round(fixed + metered, 2),
        # Pay-as-you-go so far, spread over the whole month, plus the plans.
        "projected": round(fixed + metered / today.day * days_in_month, 2),
        "day": today.day,
        "days_in_month": days_in_month,
        "daily": [round(value, 2) for value in daily],
    }
