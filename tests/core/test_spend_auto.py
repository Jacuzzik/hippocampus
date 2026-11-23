from datetime import date
from typing import Any

from core import spend_auto, spend_plans

TODAY = date(2026, 11, 23)


def _event(
    day: str, store: str, kind: str, item: str, amount: float, cur: str = "AED"
) -> dict[str, Any]:
    return {"date": day, "store": store, "kind": kind, "item": item, "amount": amount,
            "currency": cur, "subject": item, "period": "", "renews": "", "store_name": ""}  # fmt: skip


def _sub(
    name: str, store: str, price: float, status: str = "active", cur: str = "AED"
) -> dict[str, Any]:
    return {"name": name, "store": store, "store_name": "", "price": price, "currency": cur,
            "period": "month", "status": status, "renews": "", "how": "notice"}  # fmt: skip


EVENTS = [
    _event("2026-11-02", "apple", "subscription", "Claude Pro", 79.0),
    _event("2026-11-05", "bank", "purchase", "SPOTIFY", 21.99),
    _event("2026-11-10", "paypal", "sale", "You received a payment", 300.0),
    _event("2026-10-10", "paypal", "sale", "You received a payment", 100.0),
    _event("2026-11-12", "paypal", "subscription", "Canva Pro", 40.0),
    _event("2026-11-12", "google", "purchase", "Game", 9.0, "USD"),
]
FOUND = [
    _sub("Claude Pro", "apple", 79.0),
    _sub("SPOTIFY", "bank", 21.99),
    _sub("Canva Pro", "paypal", 40.0),
    _sub("Old App", "google", 5.0, status="inactive"),
    _sub("US Thing", "google", 3.0, cur="USD"),
    _sub("Netflix", "other", 39.0),
]


def test_found_rows_fill_plans_subscriptions_overview_and_wallets() -> None:
    plans = {
        "currency": "USD",
        "plans": [],
        "subs": [
            {
                "name": "netflix",
                "store": "other",
                "price": 39.0,
                "period": "month",
                "renews": "",
                "status": "active",
                "link": "",
            }
        ],  # fmt: skip
        "wallets": [
            {
                "name": "PayPal biz",
                "kind": "paypal",
                "balance": 400.0,
                "currency": "AED",
                "updated": "2026-11-01",
                "link": "",
            }
        ],  # fmt: skip
        "hidden": ["Old App"],
    }
    merged = spend_auto.fill(plans, FOUND, EVENTS, fresh=True)
    assert merged["currency"] == "AED"  # nothing saved yet, so the receipts' currency is used
    assert [(p["name"], p["provider"], p["monthly"]) for p in merged["plans"]] == [
        ("Claude Pro", "claude", 79.0)  # an AI service becomes a plan
    ]
    # Netflix is the user's own already; Old App is hidden; the rest join, marked auto.
    assert [s["name"] for s in merged["subs"]] == ["netflix", "SPOTIFY", "Canva Pro", "US Thing"]
    report = spend_plans.report(merged, {"providers": [], "days": 0}, TODAY)
    # 79 (plan) + 39 + 21.99 + 40; the USD subscription is shown but not added.
    assert report["fixed"] == 179.99 and report["subs_monthly"] == 100.99
    history = spend_auto.history(EVENTS, "AED", TODAY)
    assert history[-1] == {"month": "2026-11", "spent": 140.99, "received": 300.0}
    assert history[-2]["received"] == 100.0 and len(history) == 12
    wallets = spend_auto.wallets(merged, report["subs"], EVENTS, FOUND, TODAY)
    paypal = wallets[0]
    assert (paypal["name"], paypal["received_month"], paypal["received_year"]) == (
        "PayPal biz", 300.0, 400.0,
    )  # fmt: skip
    assert paypal["pays_for"] == ["Canva Pro"] and paypal["covers_months"] == 10.0
    bank = next(w for w in wallets if w["kind"] == "bank")
    assert bank["auto"] and bank["spent_month"] == 21.99 and bank["pays_for"] == ["SPOTIFY"]
    # Hiding a found wallet keeps it out.
    hidden = spend_auto.wallets(
        {**merged, "hidden": ["wallet:Bank"]}, report["subs"], EVENTS, FOUND, TODAY
    )
    assert all(w["kind"] != "bank" for w in hidden)


def test_hidden_list_is_saved_with_the_plans() -> None:
    saved = spend_plans.check({"currency": "AED", "hidden": ["Old App", " ", "Old App"]})
    assert saved["hidden"] == ["Old App"]
