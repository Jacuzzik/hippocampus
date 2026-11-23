"""Subscriptions, purchases and sales found in the user's own email receipts.

Apple and Google Play give other apps no way to read a person's purchases, but both email a receipt
for every purchase, renewal and cancellation, and so do PayPal, Stripe, Shopify, BuiltByBit and the
big shops. This reads those emails from Gmail over IMAP with an app password the user makes and
pastes in (Google account, Security, App passwords). It only reads: the mailbox is opened read-only,
only mail from the senders below is searched, and nothing is sent, moved or marked.

What is found is a best reading of each receipt (the store, the item, the amount, the date, and for
a subscription its period and renewal date), never more than the emails say. A subscription is
active when its latest email is a charge or confirmation and it renews in the future or was charged
within its period; it is inactive when its latest email is a cancellation or expiry, or it lapsed.
"""

import email
import imaplib
import re
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from email.message import Message
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

HOST = "imap.gmail.com"
DAYS = 400
MESSAGES_MAX = 400
BODY_MAX = 20_000
SECONDS = 30

# Sender address part -> the store it is. The first match wins.
SENDERS = (
    ("email.apple.com", "apple"),
    ("apple.com", "apple"),
    ("googleplay-noreply@google.com", "google"),
    ("payments-noreply@google.com", "google"),
    ("paypal.", "paypal"),
    ("stripe.com", "stripe"),
    ("shopify.com", "shopify"),
    ("builtbybit.com", "builtbybit"),
    ("steampowered.com", "steam"),
    ("amazon.", "amazon"),
)
STORE_NAMES = {
    "apple": "Apple",
    "google": "Google Play",
    "paypal": "PayPal",
    "stripe": "Stripe",
    "shopify": "Shopify",
    "builtbybit": "BuiltByBit",
    "steam": "Steam",
    "amazon": "Amazon",
}
# Gmail's own search, so only receipts are fetched.
QUERY = (
    f"newer_than:{DAYS}d ("
    + " OR ".join(
        f"from:{s}"
        for s in (
            "apple.com",
            "googleplay-noreply@google.com",
            "payments-noreply@google.com",
            "paypal.com",
            "stripe.com",
            "shopify.com",
            "builtbybit.com",
            "steampowered.com",
            "amazon.com",
        )
    )
    + ") (receipt OR order OR subscription OR payment OR invoice OR purchase OR sale OR refund"
    " OR cancelled OR canceled OR expired OR renew)"
)

_MONEY = (
    r"(?P<cur>US\$|CA\$|A\$|\$|€|£|₹|AED|USD|EUR|GBP|INR|CAD|AUD)\s?(?P<num>\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<num2>\d[\d,]*(?:\.\d{1,2})?)\s?(?P<cur2>AED|USD|EUR|GBP|INR|CAD|AUD)\b"
)
MONEY = re.compile(_MONEY)
TOTAL = re.compile(
    r"(?:total|amount|charged|you paid|you received)[^\n\d$€£₹]{0,40}?(" + _MONEY + ")", re.I
)
DATE_WORDS = r"([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}|\d{1,2} [A-Z][a-z]{2,8}\.? \d{4})"
RENEWS = re.compile(r"renew(?:s|al date|s on)?:?\s*(?:on\s*)?" + DATE_WORDS, re.I)
SUB_NAME = (
    re.compile(
        r"subscription (?:to|for) ([^\n.,!]{2,60}?)(?= has | is | was | will |[\n.,!(]|$)", re.I
    ),
    re.compile(r"your ([^\n.,!]{2,60}?) subscription", re.I),
)
CURRENCY = {
    "$": "USD", "US$": "USD", "CA$": "CAD", "A$": "AUD", "€": "EUR", "£": "GBP", "₹": "INR",
}  # fmt: skip

SALE = ("you received a payment", "you've got money", "payment received", "new order", "sold",
        "purchased your", "new sale", "placed by", "has been paid")  # fmt: skip
REFUND = ("refund",)
ENDED = ("cancelled", "canceled", "has expired", "expired", "has ended", "will end", "won't renew",
         "will not renew")  # fmt: skip
SUBSCRIBED = ("subscription", "renews", "auto-renewing", "renewal", "free trial", "subscribed")


class MailError(ValueError):
    pass


def _day(text: str) -> str:
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text.replace(".", ""), fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _text(msg: Message) -> str:
    """The message's readable text: its plain part, or its HTML with the tags taken out."""
    plain = html = ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        kind = part.get_content_type()
        if kind not in ("text/plain", "text/html") or part.get_filename():
            continue
        try:
            body = part.get_content()
        except (LookupError, ValueError):
            body = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        if kind == "text/plain" and not plain:
            plain = str(body)
        elif kind == "text/html" and not html:
            html = str(body)
    if not plain and html:
        html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
        html = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|td|li|h\d)>", "\n", html)
        plain = re.sub(r"<[^>]+>", " ", html)
        plain = re.sub(r"&nbsp;", " ", plain)
        plain = re.sub(r"&amp;", "&", plain)
    plain = re.sub(r"[ \t\r\f\v]+", " ", plain)
    plain = re.sub(r"\n\s*\n+", "\n", plain)
    return plain[:BODY_MAX]


def _money(text: str) -> tuple[float, str] | None:
    found = TOTAL.search(text) or MONEY.search(text)
    if not found:
        return None
    inner = MONEY.search(found.group(0)) if found.re is TOTAL else found
    if inner is None:
        return None
    raw = inner.group("num") or inner.group("num2") or "0"
    cur = inner.group("cur") or inner.group("cur2") or ""
    try:
        amount = float(raw.replace(",", ""))
    except ValueError:
        return None
    return amount, CURRENCY.get(cur, cur)


def _period(text: str) -> str:
    low = text.lower()
    if re.search(r"\b(yearly|annual|annually|per year|/ ?yr|/ ?year|1 year)\b", low):
        return "year"
    if re.search(r"\b(weekly|per week|/ ?wk|/ ?week|1 week)\b", low):
        return "week"
    return "month"


def _item(subject: str, text: str, store: str) -> str:
    for pattern in SUB_NAME:
        found = pattern.search(subject) or pattern.search(text)
        if found:
            return found.group(1).strip(" :-")
    # An Apple or Google receipt lists the item on the line before its price or its renewal date.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if (RENEWS.search(line) or MONEY.fullmatch(line)) and i > 0:
            candidate = lines[i - 1]
            if 2 < len(candidate) <= 80 and not MONEY.search(candidate):
                return candidate
    cleaned = re.sub(r"(?i)^(re:|fwd?:)\s*", "", subject).strip()
    return cleaned[:80] or STORE_NAMES.get(store, store)


def read_message(raw: bytes) -> dict[str, Any] | None:
    """One email as a found event, or None when it is not from a known store."""
    msg = email.message_from_bytes(raw, policy=default_policy)
    sender = parseaddr(str(msg.get("From", "")))[1].lower()
    store = next((name for part, name in SENDERS if part in sender), "")
    if not store:
        return None
    subject = str(msg.get("Subject", ""))
    try:
        when = parsedate_to_datetime(str(msg.get("Date"))).date().isoformat()
    except (TypeError, ValueError):
        when = ""
    text = _text(msg)
    low = f"{subject}\n{text}".lower()
    if any(word in low for word in REFUND):
        kind = "refund"
    elif any(word in low for word in SALE) and store not in ("apple", "google", "steam", "amazon"):
        kind = "sale"
    elif any(word in subject.lower() for word in ENDED) or (
        any(word in low for word in ENDED) and "subscription" in low
    ):
        kind = "ended"
    elif any(word in low for word in SUBSCRIBED):
        kind = "subscription"
    else:
        kind = "purchase"
    money = _money(text) or _money(subject)
    renews = RENEWS.search(text)
    return {
        "date": when,
        "store": store,
        "kind": kind,
        "item": _item(subject, text, store),
        "subject": subject[:200],
        "amount": money[0] if money else None,
        "currency": money[1] if money else "",
        "period": _period(low) if kind in ("subscription", "ended") else "",
        "renews": _day(renews.group(1)) if renews else "",
    }


def _key(event: dict[str, Any]) -> tuple[str, str]:
    return event["store"], re.sub(r"[^a-z0-9]+", " ", event["item"].lower()).strip()


PERIOD_DAYS = {"week": 7, "month": 31, "year": 366}


def summarise(events: Iterable[dict[str, Any]], today: date) -> dict[str, Any]:
    """Subscriptions with their state, and the latest purchases, sales and refunds."""
    ordered = sorted(events, key=lambda e: e["date"])
    subs: dict[tuple[str, str], dict[str, Any]] = {}
    for event in ordered:
        if event["kind"] not in ("subscription", "ended"):
            continue
        row = subs.setdefault(
            _key(event),
            {"name": event["item"], "store": event["store"], "price": None, "currency": ""},
        )
        if event["kind"] == "subscription":
            if event["amount"] is not None:
                row["price"], row["currency"] = event["amount"], event["currency"]
            row["period"] = event["period"] or row.get("period", "month")
            row["last"] = event["date"]
            row["renews"] = event["renews"] or ""
            row["ended"] = ""
        else:
            row["ended"] = event["date"]
            row.setdefault("period", event["period"] or "month")
            row.setdefault("last", "")
            row.setdefault("renews", event["renews"] or "")
    rows = []
    for row in subs.values():
        renews = row.get("renews", "")
        last = row.get("last", "")
        lapsed = not last or (
            date.fromisoformat(last) + timedelta(days=PERIOD_DAYS[row["period"]] + 7) < today
        )
        if row.get("ended") and row["ended"] >= last:
            status = "cancelled" if renews and renews >= today.isoformat() else "inactive"
        elif renews and renews >= today.isoformat():
            status = "active"
        else:
            status = "inactive" if lapsed else "active"
        rows.append({**row, "status": status})
    rows.sort(key=lambda r: (r["status"] != "active", r["name"].lower()))

    def latest(kind: str) -> list[dict[str, Any]]:
        return [
            {k: e[k] for k in ("date", "store", "item", "amount", "currency", "subject")}
            for e in reversed(ordered)
            if e["kind"] == kind
        ][:30]

    return {
        "subscriptions": rows,
        "purchases": latest("purchase"),
        "sales": latest("sale"),
        "refunds": latest("refund"),
    }


Fetch = Callable[[str, str], list[bytes]]


def fetch(address: str, password: str) -> list[bytes]:
    """The receipt emails, newest last, read-only. Raises MailError with a plain reason."""
    try:
        box = imaplib.IMAP4_SSL(HOST, timeout=SECONDS)
    except OSError as error:
        raise MailError(f"Could not reach Gmail: {error}.") from error
    try:
        try:
            box.login(address, password)
        except imaplib.IMAP4.error as error:
            raise MailError(
                "Gmail refused the sign-in. Use an app password (Google account, Security, App"
                " passwords; 2-Step Verification must be on), not your normal password, and check"
                " that IMAP is on in Gmail's settings."
            ) from error
        for folder in ('"[Gmail]/All Mail"', "INBOX"):
            state, _ = box.select(folder, readonly=True)
            if state == "OK":
                break
        else:
            raise MailError("Could not open the mailbox.")
        state, data = box.uid("SEARCH", "X-GM-RAW", f'"{QUERY}"')
        if state != "OK":
            raise MailError("Gmail did not accept the search.")
        uids = (data[0] or b"").split()[-MESSAGES_MAX:]
        found: list[bytes] = []
        for start in range(0, len(uids), 50):
            batch = b",".join(uids[start : start + 50])
            state, parts = box.uid("FETCH", batch, "(BODY.PEEK[])")
            if state != "OK":
                continue
            found += [p[1] for p in parts if isinstance(p, tuple) and len(p) > 1]
        return found
    finally:
        try:
            box.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def scan(address: str, password: str, today: date, get: Fetch = fetch) -> dict[str, Any]:
    raws = get(address, password)
    events = [e for e in (read_message(raw) for raw in raws) if e is not None]
    return {
        "account": address,
        "scanned_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "messages": len(events),
        **summarise(events, today),
    }
