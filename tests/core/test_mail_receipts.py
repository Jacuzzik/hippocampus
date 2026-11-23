import base64
import io
import json
import zipfile
from datetime import date
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from core import mail_receipts


def _mail(sender: str, subject: str, body: str, when: str, bulk: bool = False) -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["Subject"] = subject
    msg["Date"] = when
    if bulk:
        msg["List-Unsubscribe"] = "<https://example.com/unsubscribe>"
    msg.set_content(body)
    return msg.as_bytes()


APPLE_RENEW = _mail(
    "Apple <no_reply@email.apple.com>",
    "Your receipt from Apple.",
    "Billed to me\nPhotoApp Pro\nPhotoApp Pro (Monthly)\nRenews Dec 20, 2026\n$4.99\nTotal $4.99",
    "Fri, 20 Nov 2026 10:00:00 +0000",
)
GOOGLE_SUB = _mail(
    "Google Play <googleplay-noreply@google.com>",
    "Your subscription to Calm Notes",
    "Auto-renewing subscription\nCalm Notes (Calm Inc.)\nAED 19.99/month\nTotal: AED 19.99",
    "Mon, 02 Mar 2026 09:00:00 +0000",
)
GOOGLE_CANCEL = _mail(
    "Google Play <googleplay-noreply@google.com>",
    "Your subscription to Calm Notes has been cancelled",
    "Your subscription to Calm Notes has been cancelled. It ended on Apr 2, 2026.",
    "Thu, 02 Apr 2026 09:00:00 +0000",
)
GOOGLE_BUY = _mail(
    "Google Play <googleplay-noreply@google.com>",
    "Your Google Play Order Receipt from Nov 3, 2026",
    "Order number: GPA.1\nCity Builder\n$2.99\nTotal: $2.99",
    "Tue, 03 Nov 2026 12:00:00 +0000",
)
PAYPAL_SALE = _mail(
    "service@paypal.com",
    "You received a payment",
    "Ada Lovelace sent you $25.00 USD.\nAmount received $25.00 USD",
    "Sat, 21 Nov 2026 08:00:00 +0000",
)
SHOPIFY_SALE = _mail(
    "Voltverse <mailer@shopify.com>",
    "[Voltverse] Order #1001 placed by Sam",
    "Order summary\nPlanter x 1\nTotal AED 89.00",
    "Sun, 22 Nov 2026 08:00:00 +0000",
)
# Adverts: they name prices and "renews", but they are not receipts.
ADVERTS = [
    _mail(
        "Apple <News@insideapple.apple.com>",
        "Try Apple Music free for 1 month",
        "Then $10.99/month. Plan renews automatically.",
        "Sun, 22 Nov 2026 08:00:00 +0000",
        bulk=True,
    ),
    _mail(
        "Netflix <info@mailer.netflix.com>",
        "New on Netflix this week",
        "Plans from AED 29.00 a month.",
        "Sun, 22 Nov 2026 08:00:00 +0000",
    ),
    _mail(
        "Spotify <no-reply@spotify.com>",
        "Premium for everyone",
        "Total AED 0.00 for 3 months",
        "Sun, 22 Nov 2026 08:00:00 +0000",
        bulk=True,
    ),
]
NETFLIX = [
    _mail(
        "Netflix <info@account.netflix.com>",
        "Your receipt for Netflix",
        f"Invoice number: NF-{n}9911\nAmount charged AED 39.00",
        f"Sat, 10 {month} 2026 08:00:00 +0000",
    )
    for n, month in ((1, "Sep"), (2, "Oct"), (3, "Nov"))
]


def test_each_receipt_is_read_as_a_store_a_kind_an_item_and_an_amount() -> None:
    apple = mail_receipts.read_message(APPLE_RENEW)
    assert apple is not None
    assert (apple["store"], apple["kind"], apple["amount"], apple["currency"]) == (
        "apple",
        "subscription",
        4.99,
        "USD",
    )
    assert (apple["item"], apple["renews"], apple["period"]) == (
        "PhotoApp Pro (Monthly)",
        "2026-12-20",
        "month",
    )
    google = mail_receipts.read_message(GOOGLE_SUB)
    assert google is not None and (google["item"], google["amount"], google["currency"]) == (
        "Calm Notes",
        19.99,
        "AED",
    )
    buy = mail_receipts.read_message(GOOGLE_BUY)
    assert buy is not None and (buy["kind"], buy["amount"]) == ("purchase", 2.99)
    sale = mail_receipts.read_message(PAYPAL_SALE)
    assert sale is not None and (sale["kind"], sale["amount"]) == ("sale", 25.0)
    shop = mail_receipts.read_message(SHOPIFY_SALE)
    assert shop is not None and (shop["kind"], shop["amount"], shop["currency"]) == (
        "sale",
        89.0,
        "AED",
    )
    assert [mail_receipts.read_message(a) for a in ADVERTS] == [None, None, None]
    netflix = mail_receipts.read_message(NETFLIX[0])
    assert netflix is not None and (netflix["store_name"], netflix["item"], netflix["amount"]) == (
        "Netflix",
        "Netflix",
        39.0,
    )


def test_a_subscription_is_active_or_inactive_from_its_latest_email() -> None:
    found = mail_receipts.scan(
        "me@gmail.com",
        "app-password",
        date(2026, 11, 23),
        lambda _a, _p: [
            APPLE_RENEW, GOOGLE_SUB, GOOGLE_CANCEL, GOOGLE_BUY, PAYPAL_SALE, *ADVERTS, *NETFLIX
        ],
    )  # fmt: skip
    subs = {row["name"]: (row["status"], row["how"]) for row in found["subscriptions"]}
    assert subs == {
        "PhotoApp Pro (Monthly)": ("active", "notice"),
        "Netflix": ("active", "repeated charges"),  # charged monthly, never says "subscription"
        "Calm Notes": ("inactive", "notice"),
    }
    assert [p["item"] for p in found["purchases"]] == ["City Builder"]  # not the Netflix charges
    assert [s["amount"] for s in found["sales"]] == [25.0]
    assert (found["read"], found["messages"]) == (11, 8)


def test_connect_keeps_the_password_in_the_keychain_and_scans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai import keys, network
    from core.session_mail import MailPart

    saved: dict[str, str] = {}
    monkeypatch.setattr(keys, "set_key", lambda name, value: saved.__setitem__(name, value))
    monkeypatch.setattr(keys, "get_key", lambda name: saved.get(name))
    monkeypatch.setattr(keys, "clear_key", lambda name: saved.pop(name, None))
    monkeypatch.setattr(network, "mode", lambda: "converse")

    class Part(MailPart):
        storage = tmp_path
        notes: list[str] = []

        def note(self, _kind: str, **fields: Any) -> None:
            self.notes.append(fields["text"])

    part = Part()
    part._mail_fetch = lambda _a, password: [APPLE_RENEW] if password == "abcdabcdabcdabcd" else []
    with pytest.raises(ValueError, match="Gmail address"):
        part.mail_connect({"email": "nope", "password": "abcdabcdabcdabcd"})
    state = part.mail_connect({"email": "me@gmail.com", "password": "abcd abcd abcd abcd"})
    assert state["connected"] and state["found"]["subscriptions"][0]["status"] == "active"
    assert "abcd" not in (tmp_path / "mail.json").read_text()  # the password is never in a file
    # A downloaded file joins the email: the bank statement's monthly Spotify charge is found.
    data = base64.b64encode(BANK.encode()).decode()
    state = part.purchases_import({"name": "statement.csv", "data": data})
    names = {s["name"].lower() for s in state["found"]["subscriptions"]}
    assert any("spotify" in n for n in names) and "photoapp pro (monthly)" in names
    assert part.purchases_remove({"name": "statement.csv"})["files"] == []
    assert part.mail_disconnect()["connected"] is False
    assert not (tmp_path / "mail.json").exists()


BANK = """Account: 1234 5678
Date,Description,Amount
2026-08-14,SPOTIFY P1234 STOCKHOLM,-21.99
2026-09-14,SPOTIFY P1299 STOCKHOLM,-21.99
2026-10-14,SPOTIFY P1300 STOCKHOLM,-21.99
2026-11-14,SPOTIFY P1301 STOCKHOLM,-21.99
2026-11-02,CARREFOUR MALL,-150.20
2026-11-03,SALARY,+5000
"""


def _takeout() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(
            "Takeout/Google Play Store/Subscriptions.json",
            json.dumps([
                {"subscription": {"doc": {"title": "YouTube Premium"}, "state": "ACTIVE",
                                  "renewalDate": "2026-12-05T00:00:00Z",
                                  "pricing": [{"period": "P1M", "price": "AED 26.00"}]}},
                {"subscription": {"doc": {"title": "Old Game Pass"}, "state": "CANCELED",
                                  "expirationDate": "2026-01-05T00:00:00Z"}},
            ]),
        )  # fmt: skip
        archive.writestr(
            "Takeout/Google Play Store/Order History.json",
            json.dumps([
                {"orderHistory": {"orderId": "GPA.33", "creationTime": "2026-10-01T10:00:00Z",
                                  "lineItem": [{"doc": {"title": "City Builder"}}],
                                  "totalPrice": "AED 10.99"}},
            ]),
        )  # fmt: skip
    return out.getvalue()


def test_takeout_and_bank_files_give_subscriptions_and_purchases() -> None:
    from core import purchase_files

    events = purchase_files.read("takeout-2026.zip", _takeout())
    found = mail_receipts.summarise(events, date(2026, 11, 23))
    subs = {s["name"]: (s["status"], s["price"], s["store"]) for s in found["subscriptions"]}
    assert subs == {
        "YouTube Premium": ("active", 26.0, "google"),
        "Old Game Pass": ("inactive", None, "google"),
    }
    assert [(p["item"], p["amount"]) for p in found["purchases"]] == [("City Builder", 10.99)]
    bank = mail_receipts.summarise(
        purchase_files.read("statement.csv", BANK.encode()), date(2026, 11, 23)
    )
    assert [(s["status"], s["how"], s["charges"]) for s in bank["subscriptions"]] == [
        ("active", "repeated charges", 4)
    ]
    assert [p["amount"] for p in bank["purchases"]] == [150.2]  # salary is money in, left out
    with pytest.raises(ValueError, match="Nothing that looks"):
        purchase_files.read("notes.csv", b"a,b\n1,2\n")
