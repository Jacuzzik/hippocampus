"""Subscriptions, purchases and sales found in the user's own email receipts.

Apple and Google Play give other apps no way to read a person's purchases, but both email a receipt
for every purchase, renewal and cancellation, and so does nearly every other shop and service. This
reads those emails from Gmail over IMAP with an app password the user makes and pastes in (Google
account, Security, App passwords). It only reads: the mailbox is opened read-only and nothing is
sent, moved or marked.

Only real receipts and account notices count. Gmail's own sorting leaves out Promotions, Social and
Forums, and each email must then show it is a transaction: an order, invoice or receipt number with
an amount, a labelled total that was charged or paid, or a plain subscription notice (confirmed,
renews on, cancelled, expired). Anything that reads like an advert (a discount, "try it free", a
mailing-list email with no order number) is dropped. What is read from each receipt (the store, the
item, the amount, the date, the period and renewal date) is never more than the email says.

Subscriptions are then worked out from all the events together (see `summarise`): from notices, and
from the same thing being charged again and again at a steady interval, which also finds the ones
whose emails never say "subscription".
"""

import email
import imaplib
import re
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from email.message import Message
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime
from statistics import median
from typing import Any

HOST = "imap.gmail.com"
DAYS = 730
MESSAGES_MAX = 800
BODY_MAX = 20_000
SECONDS = 30

# Sender address part -> the store it is. The first match wins; any other sender is named after
# the name it sends as (Netflix, Spotify, ...).
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
SALE_STORES = ("paypal", "stripe", "shopify", "builtbybit")
_KNOWN = (
    "email.apple.com", "googleplay-noreply@google.com", "payments-noreply@google.com",
    "paypal.com", "stripe.com", "shopify.com", "builtbybit.com", "steampowered.com", "amazon.com",
)  # fmt: skip
# Gmail's own search: the Purchases category, the known stores, or a receipt-like subject, and
# never what Gmail sorted into Promotions, Social or Forums.
QUERY = (
    f"newer_than:{DAYS}d -category:promotions -category:social -category:forums ("
    "category:purchases OR "
    + " OR ".join(f"from:{s}" for s in _KNOWN)
    + ' OR subject:(receipt OR invoice OR "order confirmation" OR "your order" OR subscription'
    ' OR renewal OR renew OR membership OR "payment received" OR "you received" OR refund'
    " OR cancelled OR canceled OR expired OR charged OR billing))"
)

_MONEY = (
    r"(?P<cur>US\$|CA\$|A\$|\$|€|£|₹|AED|USD|EUR|GBP|INR|CAD|AUD|SAR)\s?"
    r"(?P<num>\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<num2>\d[\d,]*(?:\.\d{1,2})?)\s?(?P<cur2>AED|USD|EUR|GBP|INR|CAD|AUD|SAR)\b"
)
MONEY = re.compile(_MONEY)
TOTAL = re.compile(
    r"(?:total|amount (?:paid|charged|received|due)|charged|you paid|you received|billed)"
    r"[^\n\d$€£₹]{0,40}?(" + _MONEY + ")",
    re.I,
)
ORDER_ID = re.compile(
    r"\b(?:order|invoice|receipt|transaction|document|reference|confirmation)"
    r"\s*(?:id|number|no\.?|#|ref)\s*[:#]?\s*#?[A-Z0-9][A-Z0-9.\-]{3,}",
    re.I,
)
DATE_WORDS = (
    r"([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}|\d{1,2} [A-Z][a-z]{2,8}\.? \d{4}|\d{4}-\d{2}-\d{2})"
)
RENEWS = re.compile(
    r"(?:renew(?:s|al date|s on)?|next (?:billing|payment|charge)(?: date)?)\s*:?\s*(?:on\s*)?"
    + DATE_WORDS,
    re.I,
)
ENDS_ON = re.compile(r"(?:ends?|ended|expires?|expired|until)\s*(?:on\s*)?:?\s*" + DATE_WORDS, re.I)
SUB_NAME = (
    re.compile(
        r"subscription (?:to|for) ([^\n.,!]{2,60}?)(?= has | is | was | will |[\n.,!(]|$)", re.I
    ),
    re.compile(r"your ([^\n.,!]{2,60}?) (?:subscription|membership)", re.I),
)
CURRENCY = {
    "$": "USD", "US$": "USD", "CA$": "CAD", "A$": "AUD", "€": "EUR", "£": "GBP", "₹": "INR",
}  # fmt: skip

# A subscription notice, said plainly: these are what services send about an account, not adverts.
CONFIRMED = re.compile(
    r"subscription confirmation|you(?:'re| are| have)? (?:now )?subscribed|thanks? (?:you )?for"
    r" subscribing|your (?:subscription|membership|plan)(?: to [^\n.]{2,60})? (?:has been |is |was )"
    r"(?:confirmed|renewed|activated|active|started)|free trial (?:has )?(?:started|begins)"
    r"|subscription (?:has been |was )?renewed|membership (?:has been |was )?renewed",
    re.I,
)
RENEWING = re.compile(
    r"will (?:automatically )?renew|\brenews\b|auto-renew|next (?:billing|payment"
    r"|charge)|billed (?:monthly|yearly|annually|every)|renewal (?:date|receipt|notice)",
    re.I,
)
ENDED = re.compile(
    r"(?:subscription|membership|plan|trial)[^\n.]{0,60}?(?:has been |was |is |will be )?"
    r"(?:cancel+ed|ended|expired|expiring|terminated)|will not (?:auto-?)?renew|won'?t (?:auto-?)?"
    r"renew|cancell?ation (?:confirmed|confirmation|request)|you(?:'ve| have) cancel+ed",
    re.I,
)
REFUNDED = re.compile(r"\brefund(?:ed)?\b|has been refunded|refund of", re.I)
SALE = re.compile(
    r"you received a payment|you've got money|payment received|you made a sale|new sale"
    r"|purchased your|placed by|new order|has been paid|you received \S+ from",
    re.I,
)
# Adverts and newsletters. One of these with no order number drops the email.
MARKETING = re.compile(
    r"\d{1,2} ?% off|\bsale ends|\bdeals?\b|special offer|limited[- ]time|\btry (?:[\w+]+ ){0,3}free"
    r"|free for \d|get \d+ months?|\bintroducing\b|new on |\bdiscover\b|don'?t miss|last chance"
    r"|save up to|upgrade now|come back|we miss you|recommended for you|newsletter|webinar"
    r"|black friday|cyber monday|exclusive offer|\bpromo\b|coupon|unlock |start your free",
    re.I,
)
RECEIPT_SUBJECT = re.compile(
    r"receipt|invoice|order|payment|charged|purchase|renew|subscription|membership|refund|sale"
    r"|sold|paid|billing|cancel|expire|trial",
    re.I,
)


class MailError(ValueError):
    pass


def _day(text: str) -> str:
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
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


def _amount(found: re.Match[str]) -> tuple[float, str] | None:
    raw = found.group("num") or found.group("num2") or "0"
    cur = found.group("cur") or found.group("cur2") or ""
    try:
        return float(raw.replace(",", "")), CURRENCY.get(cur, cur)
    except ValueError:
        return None


def _money(text: str, labelled_only: bool) -> tuple[float, str] | None:
    """The total: a labelled one (Total, Charged, You paid), else the first amount when allowed."""
    total = TOTAL.search(text)
    if total:
        inner = MONEY.search(total.group(0))
        return _amount(inner) if inner else None
    if labelled_only:
        return None
    first = MONEY.search(text)
    return _amount(first) if first else None


def _period(text: str) -> str:
    low = text.lower()
    if re.search(r"\b(yearly|annual|annually|per year|/ ?yr|/ ?year|1 year|12 months)\b", low):
        return "year"
    if re.search(r"\b(weekly|per week|/ ?wk|/ ?week|1 week)\b", low):
        return "week"
    if re.search(r"\b(monthly|per month|/ ?mo|/ ?month|1 month|every month)\b", low):
        return "month"
    return ""


def _item(subject: str, text: str, store_name: str) -> str:
    for pattern in SUB_NAME:
        found = pattern.search(subject) or pattern.search(text)
        if found and not MONEY.search(found.group(1)):
            return found.group(1).strip(" :-")
    # An Apple or Google receipt lists the item on the line before its price or its renewal date.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if (RENEWS.search(line) or MONEY.fullmatch(line)) and i > 0:
            candidate = lines[i - 1]
            if 2 < len(candidate) <= 80 and not MONEY.search(candidate):
                return candidate
    if store_name.lower() not in ("apple", "google play", "amazon", "paypal", "steam"):
        return store_name  # Netflix, Spotify and the like: the service is the thing paid for
    cleaned = re.sub(r"(?i)^(re:|fwd?:)\s*", "", subject).strip()
    return cleaned[:80] or store_name


def _sender_store(msg: Message) -> tuple[str, str]:
    """(store key, store name) from the From line."""
    name, address = parseaddr(str(msg.get("From", "")))
    address = address.lower()
    for part, key in SENDERS:
        if part in address:
            return key, STORE_NAMES[key]
    shown = re.sub(r"(?i)\b(team|support|billing|no-?reply|noreply|receipts?|payments?|info|"
                   r"account|accounts|customer service|via .*)\b", "", name)  # fmt: skip
    shown = re.sub(r"[\"'<>|]+", "", shown).strip(" -·,")
    domain = address.rsplit("@", 1)[-1].split(".")
    label = domain[-2] if len(domain) >= 2 else domain[0]
    shown = shown or label.capitalize()
    return re.sub(r"[^a-z0-9]+", "", shown.lower()) or label, shown[:40]


def read_message(raw: bytes) -> dict[str, Any] | None:
    """One email as a found event, or None when it is not a receipt or an account notice."""
    msg = email.message_from_bytes(raw, policy=default_policy)
    store, store_name = _sender_store(msg)
    subject = str(msg.get("Subject", ""))
    try:
        when = parsedate_to_datetime(str(msg.get("Date"))).date().isoformat()
    except (TypeError, ValueError):
        when = ""
    text = _text(msg)
    both = f"{subject}\n{text}"
    has_order = bool(ORDER_ID.search(both))
    confirmed, renewing, ended = CONFIRMED.search(both), RENEWING.search(both), ENDED.search(both)
    notice = bool(confirmed or renewing or ended)
    advert = bool(MARKETING.search(subject)) or (
        bool(msg.get("List-Unsubscribe")) and not has_order and not RECEIPT_SUBJECT.search(subject)
    )
    if advert and not has_order:
        return None
    money = _money(text, labelled_only=not has_order) or _money(subject, labelled_only=True)
    charged = money is not None and (has_order or bool(RECEIPT_SUBJECT.search(subject)))
    if not (charged or (notice and RECEIPT_SUBJECT.search(subject))):
        return None
    sale_store = store in SALE_STORES
    if REFUNDED.search(subject) or (REFUNDED.search(text) and money and not notice):
        kind = "refund"
    elif sale_store and SALE.search(both):
        kind = "sale"
    elif ended and not confirmed:
        kind = "ended"
    elif notice or re.search(r"(?i)subscription|membership", subject):
        kind = "subscription"
    else:
        kind = "purchase"
    renews = RENEWS.search(text)
    ends = ENDS_ON.search(text) if kind == "ended" else None
    return {
        "date": when,
        "store": store,
        "store_name": store_name,
        "kind": kind,
        "item": _item(subject, text, store_name),
        "subject": subject[:200],
        "amount": money[0] if money and kind != "ended" else None,
        "currency": money[1] if money and kind != "ended" else "",
        "period": _period(both),
        "renews": _day(renews.group(1)) if renews else (_day(ends.group(1)) if ends else ""),
        "source": "email",
    }


PERIOD_DAYS = {"week": 7, "month": 31, "year": 366}
GRACE_DAYS = 7


def _key(event: dict[str, Any]) -> tuple[str, str]:
    item = re.sub(r"\((?:monthly|yearly|annual|weekly)\)", "", event["item"].lower())
    item = re.sub(r"\b\d[\d/.-]*\b", " ", item)  # dates and numbers in bank lines
    return event["store"], re.sub(r"[^a-z0-9]+", " ", item).strip()


def _steady(days: list[str]) -> str:
    """'week', 'month' or 'year' when the charges come at a steady interval, else ''."""
    when = sorted({date.fromisoformat(d) for d in days if d})
    if len(when) < 2:
        return ""
    gaps = [(b - a).days for a, b in zip(when, when[1:], strict=False)]
    gap = median(gaps)
    if not all(abs(g - gap) <= max(4, gap * 0.2) for g in gaps):
        return ""
    if 5 <= gap <= 9 and len(when) >= 3:
        return "week"
    if 26 <= gap <= 35 and len(when) >= 3:
        return "month"
    if 350 <= gap <= 380:
        return "year"
    return ""


def _close(amounts: list[float]) -> bool:
    if not amounts:
        return True
    low, high = min(amounts), max(amounts)
    return high <= low * 1.25 + 0.5


def summarise(events: Iterable[dict[str, Any]], today: date) -> dict[str, Any]:
    """Subscriptions with their state and the evidence for each, and the latest purchases, sales
    and refunds. A thing is a subscription when a notice says so, or when it was charged at least
    three times a week or a month apart (twice a year apart) for about the same amount."""
    ordered = sorted(events, key=lambda e: e["date"])
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in ordered:
        if event["kind"] in ("subscription", "ended", "purchase"):
            groups.setdefault(_key(event), []).append(event)
    rows = []
    recurring_keys: set[tuple[str, str]] = set()
    for key, group in groups.items():
        notices = [e for e in group if e["kind"] in ("subscription", "ended")]
        charges = [e for e in group if e["kind"] != "ended" and e["amount"] is not None]
        steady = (
            _steady([e["date"] for e in charges]) if _close([e["amount"] for e in charges]) else ""
        )
        if not notices and not steady:
            continue
        if not notices:
            recurring_keys.add(key)
        last_charge = max((e["date"] for e in charges), default="")
        ends = [e["date"] for e in group if e["kind"] == "ended"]
        ended = max(ends, default="")
        latest_on = [e for e in group if e["kind"] != "ended"]
        period = (
            next((e["period"] for e in reversed(group) if e["period"]), "") or steady or "month"
        )
        renews = next((e["renews"] for e in reversed(group) if e["renews"]), "")
        last_seen = max((e["date"] for e in latest_on), default="")
        price = charges[-1] if charges else None
        if ends and ended >= last_seen:
            status = "cancelled" if renews and renews >= today.isoformat() else "inactive"
        elif renews and renews >= today.isoformat():
            status = "active"
        else:
            anchor = last_charge or last_seen
            status = (
                "active"
                if anchor
                and date.fromisoformat(anchor) + timedelta(days=PERIOD_DAYS[period] + GRACE_DAYS)
                >= today
                else "inactive"
            )
        first = group[0]
        rows.append(
            {
                "name": group[-1]["item"],
                "store": first["store"],
                "store_name": first.get("store_name") or STORE_NAMES.get(first["store"], ""),
                "price": price["amount"] if price else None,
                "currency": price["currency"] if price else "",
                "period": period,
                "status": status,
                "last": last_charge,
                "renews": renews,
                "ended": ended,
                "since": first["date"],
                "charges": len(charges),
                "how": "repeated charges" if not notices else "notice",
                "sources": sorted({e.get("source", "email") for e in group}),
                "evidence": [
                    {"date": e["date"], "subject": e["subject"]} for e in reversed(group[-4:])
                ],
            }
        )
    rows.sort(key=lambda r: ({"active": 0, "cancelled": 1}.get(r["status"], 2), r["name"].lower()))

    def latest(kind: str) -> list[dict[str, Any]]:
        return [
            {
                k: e.get(k, "")
                for k in (
                    "date",
                    "store",
                    "store_name",
                    "item",
                    "amount",
                    "currency",
                    "subject",
                    "source",
                )
            }  # fmt: skip
            for e in reversed(ordered)
            if e["kind"] == kind and (kind != "purchase" or _key(e) not in recurring_keys)
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
        state, data = box.uid("SEARCH", "X-GM-RAW", '"' + QUERY.replace('"', '\\"') + '"')
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


def read_all(raws: Iterable[bytes]) -> list[dict[str, Any]]:
    return [e for e in (read_message(raw) for raw in raws) if e is not None]


def scan(address: str, password: str, today: date, get: Fetch = fetch) -> dict[str, Any]:
    raws = get(address, password)
    events = read_all(raws)
    return {
        "account": address,
        "scanned_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "read": len(raws),
        "messages": len(events),
        "events": events,
        **summarise(events, today),
    }
