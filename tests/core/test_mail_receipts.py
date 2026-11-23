from datetime import date
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from core import mail_receipts


def _mail(sender: str, subject: str, body: str, when: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["Subject"] = subject
    msg["Date"] = when
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
OTHER = _mail(
    "friend@example.com", "Your receipt", "Total $1.00", "Sun, 22 Nov 2026 08:00:00 +0000"
)


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
    assert mail_receipts.read_message(OTHER) is None  # not from a known store


def test_a_subscription_is_active_or_inactive_from_its_latest_email() -> None:
    found = mail_receipts.scan(
        "me@gmail.com",
        "app-password",
        date(2026, 11, 23),
        lambda _a, _p: [APPLE_RENEW, GOOGLE_SUB, GOOGLE_CANCEL, GOOGLE_BUY, PAYPAL_SALE, OTHER],
    )
    subs = {row["name"]: row["status"] for row in found["subscriptions"]}
    assert subs == {"PhotoApp Pro (Monthly)": "active", "Calm Notes": "inactive"}
    assert [p["item"] for p in found["purchases"]] == ["City Builder"]
    assert [s["amount"] for s in found["sales"]] == [25.0]
    assert found["messages"] == 5


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
    assert part.mail_disconnect()["connected"] is False
    assert not (tmp_path / "mail.json").exists()
