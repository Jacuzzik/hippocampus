"""Fills the Money board from what was found (Gmail receipts and added files, see session_mail).

Nothing here is saved: the user's own plans, subscriptions and wallets stay as they entered them, and
what was found is put beside them, marked "auto", each time the board is read. A found subscription
for an AI service (Claude, ChatGPT, Gemini ...) becomes a plan with its monthly price; any other one
joins the subscriptions. A wallet (PayPal, Stripe, Shopify, BuiltByBit, a bank) gets the money that
came in and went out through it, the subscriptions it pays for and how many months its balance
covers them; a service with activity but no wallet yet gets one. The user hides a found row with the
`hidden` list in the plans file. Amounts in another currency are shown but never added to a total,
because no exchange rate is guessed.
"""

import re
from collections import Counter
from datetime import date
from typing import Any

from core import spend_plans

AI = (
    (r"\bclaude\b|anthropic", "claude"),
    (r"openai api|openai, llc.*api|api usage", "openai"),
    (r"chatgpt|openai", "codex"),
    (r"gemini|google one ai|google ai (?:pro|ultra)", "gemini-cli"),
    (r"\bgrok\b|\bx\.ai\b|\bxai\b", "xai"),
    (r"mistral|le chat", "mistral"),
    (r"deepseek", "deepseek"),
    (r"openrouter", "openrouter"),
    (r"\bgroq\b", "groq"),
    (r"kimi|moonshot", "moonshot"),
    (r"cursor|copilot|perplexity|midjourney|windsurf|codeium|poe\b|character\.ai", ""),
)
# Where money found in a receipt went through: the store of the event -> the wallet kind.
WALLET_OF = {
    "paypal": "paypal",
    "stripe": "stripe",
    "builtbybit": "builtbybit",
    "shopify": "shopify",
    "bank": "bank",
}
WALLET_NAMES = {
    "paypal": "PayPal",
    "stripe": "Stripe",
    "builtbybit": "BuiltByBit",
    "shopify": "Shopify",
    "bank": "Bank",
}
STATUS = {"active": "active", "cancelled": "cancelled", "inactive": "expired"}
MONTHS = 12


def _ai(name: str) -> str | None:
    low = name.lower()
    for pattern, provider in AI:
        if re.search(pattern, low):
            return provider
    return None


def _same(a: str, b: str) -> bool:
    a, b = (
        re.sub(r"[^a-z0-9]+", " ", a.lower()).strip(),
        re.sub(r"[^a-z0-9]+", " ", b.lower()).strip(),
    )
    return bool(a and b) and (a == b or a in b or b in a)


def _counts(row: dict[str, Any], currency: str) -> bool:
    return row.get("currency", "") in ("", currency)


def _main_currency(events: list[dict[str, Any]]) -> str:
    found = Counter(
        e["currency"] for e in events if e.get("currency") in spend_plans.CURRENCIES
    ).most_common(1)
    return found[0][0] if found else ""


def fill(plans: dict[str, Any], found_subs: list[dict[str, Any]], events: list[dict[str, Any]],
         fresh: bool) -> dict[str, Any]:  # fmt: skip
    """The plans with the found rows added. `fresh` is True when the user has saved nothing yet,
    so the currency can follow the receipts."""
    currency = plans["currency"]
    if fresh:
        currency = _main_currency(events) or currency
    hidden = {h.lower() for h in plans.get("hidden", [])}
    own = [p["name"] for p in plans["plans"]] + [s["name"] for s in plans["subs"]]
    auto_plans, auto_subs = [], []
    for sub in found_subs:
        name = sub["name"][: spend_plans.NAME_MAX]
        if name.lower() in hidden or any(_same(name, mine) for mine in own):
            continue
        price = sub.get("price") or 0.0
        provider = _ai(f"{name} {sub.get('store_name', '')}")
        if provider is not None and sub["status"] == "active":
            per = {"month": 1.0, "year": 1 / 12, "week": 52 / 12}[sub["period"]]
            auto_plans.append(
                {
                    "name": name,
                    "provider": provider,
                    "monthly": round(price * per, 2),
                    "per_million": 0.0,
                    "currency": sub.get("currency", ""),
                    "auto": True,
                }
            )
            continue
        auto_subs.append(
            {
                "name": name,
                "store": sub["store"] if sub["store"] in ("apple", "google") else "other",
                "store_name": sub.get("store_name", ""),
                "price": price,
                "period": sub["period"],
                "renews": sub.get("renews", ""),
                "status": STATUS[sub["status"]],
                "link": "",
                "currency": sub.get("currency", ""),
                "auto": True,
                "how": sub.get("how", ""),
            }
        )
    return {
        **plans,
        "currency": currency,
        "plans": plans["plans"] + auto_plans,
        "subs": plans["subs"] + auto_subs,
    }


def history(events: list[dict[str, Any]], currency: str, today: date) -> list[dict[str, Any]]:
    """Money out (charges less refunds) and money in (sales) per month, the last twelve months,
    from receipts in the board's currency or with none."""
    months = []
    year, month = today.year, today.month
    for _ in range(MONTHS):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    rows = {m: {"month": m, "spent": 0.0, "received": 0.0} for m in reversed(months)}
    for e in events:
        if e.get("amount") is None or not _counts(e, currency) or e["date"][:7] not in rows:
            continue
        row = rows[e["date"][:7]]
        if e["kind"] in ("subscription", "purchase"):
            row["spent"] += e["amount"]
        elif e["kind"] == "refund":
            row["spent"] -= e["amount"]
        elif e["kind"] == "sale":
            row["received"] += e["amount"]
    return [{**r, "spent": round(r["spent"], 2), "received": round(r["received"], 2)}
            for r in rows.values()]  # fmt: skip


def wallets(plans: dict[str, Any], subs: list[dict[str, Any]], events: list[dict[str, Any]],
            found_subs: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:  # fmt: skip
    """Each wallet with what went through it, and a found one for each service with activity."""
    hidden = {h.lower() for h in plans.get("hidden", [])}
    rows = [dict(w) for w in spend_plans.wallet_rows(plans.get("wallets", []))]
    kinds_had = {w["kind"] for w in rows}
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        kind = WALLET_OF.get(e["store"])
        if kind and e.get("amount") is not None:
            by_kind.setdefault(kind, []).append(e)
    for kind, found in by_kind.items():
        name = WALLET_NAMES[kind]
        if kind in kinds_had or f"wallet:{name}".lower() in hidden:
            continue
        rows.append(
            {
                "name": name,
                "kind": kind,
                "balance": 0.0,
                "currency": _main_currency(found) or plans["currency"],
                "updated": "",
                "link": "",
                "open": spend_plans.WALLETS[kind],
                "auto": True,
            }
        )
    month, year = today.isoformat()[:7], today.isoformat()[:4]
    found_by_name = {s["name"].lower(): s for s in found_subs}
    for w in rows:
        mine = [
            e for e in by_kind.get(w["kind"], []) if e.get("currency", "") in ("", w["currency"])
        ]
        sold = [e for e in mine if e["kind"] == "sale"]
        paid = [e for e in mine if e["kind"] in ("subscription", "purchase")]
        pays = [
            s for s in subs
            if s.get("active") and _counts(s, w["currency"])
            and WALLET_OF.get((found_by_name.get(s["name"].lower()) or {}).get("store", "")) == w["kind"]
        ]  # fmt: skip
        monthly = round(sum(s["monthly"] for s in pays), 2)
        w.update(
            {
                "received_month": round(
                    sum(e["amount"] for e in sold if e["date"][:7] == month), 2
                ),
                "received_year": round(sum(e["amount"] for e in sold if e["date"][:4] == year), 2),
                "spent_month": round(sum(e["amount"] for e in paid if e["date"][:7] == month), 2),
                "last": max((e["date"] for e in mine), default=""),
                "moves": len(mine),
                "pays_for": [s["name"] for s in pays],
                "pays_monthly": monthly,
                "covers_months": round(w["balance"] / monthly, 1)
                if monthly and w["balance"]
                else None,
                "auto": bool(w.get("auto")),
            }
        )
    rows.sort(key=lambda r: (r["auto"], -r["balance"], -r["received_year"], r["name"].lower()))
    return rows
