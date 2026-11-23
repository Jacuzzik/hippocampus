"""Purchases and subscriptions from files the user downloads themselves.

Apple and Google let a person download a copy of their own data: Google Takeout's "Google Play
Store" part (Purchase History, Order History, Subscriptions) and Apple's privacy.apple.com copy
("Apple Media Services information"). A bank or card statement exported as CSV shows every charge,
including subscriptions paid by card that never email a receipt. This reads any of those, as a
.json, a .csv, or the .zip they come in, and turns each line into the same events the email reader
makes, so `mail_receipts.summarise` finds the subscriptions in them too: from what the file says
(a state, a renewal or expiry date) or from the same charge coming back at a steady interval.

The files' layouts are not published and change, so fields are found by their names (title, date,
price, state, renewal ...) rather than by a fixed layout. Nothing is sent anywhere.
"""

import csv
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from core.mail_receipts import CURRENCY, MONEY

BYTES_MAX = 30_000_000
FILES_MAX = 60
ROWS_MAX = 20_000

TITLE = ("title", "name", "description", "item", "product", "content", "app", "merchant", "payee",
         "details", "narrative", "memo")  # fmt: skip
WHEN = ("purchasetime", "creationtime", "orderdate", "purchasedate", "transactiondate",
        "date", "time", "posted", "booking")  # fmt: skip
PRICE = ("price", "pricing", "amount", "total", "cost", "debit", "charge", "paid")
STATE = ("state", "status")
RENEW = ("renew", "expir", "enddate", "nextbilling", "nextpayment", "validuntil")
SUBSCRIPTION_HINT = re.compile(r"subscri|renew|membership|recurring", re.I)
NOISE = re.compile(
    r"\b(pos|card|visa|mastercard|debit|credit|purchase|payment|ref|txn|trx|online|intl|"
    r"recurring|ecom|apple ?pay|google ?pay|www|com|ae|us|uk)\b|[*#]|\d",
    re.I,
)


def _norm(key: str) -> str:
    return re.sub(r"[^a-z]", "", key.lower())


def _pick(row: dict[str, Any], names: tuple[str, ...], skip: tuple[str, ...] = ()) -> Any:  # noqa: ANN401 (any JSON or CSV value)
    for name in names:
        for key, value in row.items():
            low = _norm(key)
            if name in low and not any(s in low for s in skip) and value not in (None, "", [], {}):
                return value
    return None


def _day(value: Any) -> str:  # noqa: ANN401 (any JSON or CSV value)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        number = float(value)
        if number > 1e11:  # milliseconds
            number /= 1000
        if 1e8 < number < 1e10:
            return datetime.fromtimestamp(number, tz=UTC).date().isoformat()
        return ""
    text = str(value).strip()
    iso = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if iso:
        return iso.group(1)
    candidates = (text, text.split(" ")[0], text[:12])
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y", "%b %d, %Y", "%d %b %Y",
                "%B %d, %Y", "%d %B %Y", "%d/%m/%y", "%m/%d/%y"):  # fmt: skip
        for candidate in candidates:
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                continue
    return ""


def _price(value: Any) -> tuple[float, str] | None:  # noqa: ANN401 (any JSON or CSV value)
    if isinstance(value, dict):
        inner = _pick(value, ("amount", "price", "value", "micros"))
        cur = str(_pick(value, ("currency",)) or "")
        if inner is None:
            return None
        amount = _price(inner)
        if amount and "micros" in json.dumps(value).lower() and amount[0] > 10_000:
            amount = (amount[0] / 1_000_000, amount[1])
        return (amount[0], cur or amount[1]) if amount else None
    if isinstance(value, list):
        return _price(value[0]) if value else None
    if isinstance(value, (int, float)):
        return abs(float(value)), ""
    text = str(value).strip()
    found = MONEY.search(text)
    if found:
        raw = found.group("num") or found.group("num2") or "0"
        cur = found.group("cur") or found.group("cur2") or ""
        return abs(float(raw.replace(",", ""))), CURRENCY.get(cur, cur)
    plain = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    if not plain:
        return None
    return abs(float(plain.group(0).replace(",", ""))), ""


def _title(row: dict[str, Any]) -> str:
    direct = _pick(row, TITLE)
    if isinstance(direct, str):
        return direct.strip()[:80]
    for value in row.values():  # Takeout puts it one level down: doc.title, lineItem[0].doc.title
        inner = value[0] if isinstance(value, list) and value else value
        if isinstance(inner, dict):
            found = _title(inner)
            if found:
                return found
    return ""


def _store(path: str) -> tuple[str, str]:
    low = path.lower()
    if "play" in low or "takeout" in low or "google" in low:
        return "google", "Google Play"
    if "apple" in low or "itunes" in low or "app store" in low:
        return "apple", "Apple"
    return "bank", PurePosixPath(path).stem[:40] or "Statement"


def _event(row: dict[str, Any], store: tuple[str, str], bank: bool) -> dict[str, Any] | None:
    title = _title(row)
    when = _day(_pick(row, WHEN, RENEW) or "")
    money = _price(_pick(row, PRICE)) if _pick(row, PRICE) is not None else None
    state = str(_pick(row, STATE) or "").lower()
    renew = _day(_pick(row, RENEW) or "")
    if not title or not (when or money or state or renew):
        return None
    if bank:
        credit = _pick(row, ("credit", "deposit", "moneyin"))
        debit = _pick(row, ("debit", "withdrawal", "moneyout"))
        raw_amount = str(_pick(row, ("amount",)) or "")
        if credit and not debit:
            return None  # money in, not a charge
        if raw_amount.strip().startswith("+"):
            return None
        title = re.sub(r"\s+", " ", NOISE.sub(" ", title)).strip(" -.,") or title
    whole = json.dumps(row, default=str)
    is_sub = bool(SUBSCRIPTION_HINT.search(whole)) or bool(renew)
    ended = any(w in state for w in ("cancel", "expired", "ended", "inactive", "terminated"))
    kind = "ended" if is_sub and ended else "subscription" if is_sub else "purchase"
    if "refund" in whole.lower() and not is_sub:
        kind = "refund"
    period_text = whole.lower()
    period = (
        "year" if re.search(r"p1y|year|annual", period_text)
        else "week" if re.search(r"p1w|weekly", period_text)
        else "month" if re.search(r"p1m|month", period_text)
        else ""
    )  # fmt: skip
    return {
        "date": when,
        "store": store[0],
        "store_name": store[1],
        "kind": kind,
        "item": title,
        "subject": f"{title} ({state or kind})"[:200],
        "amount": money[0] if money and kind != "ended" else None,
        "currency": money[1] if money and kind != "ended" else "",
        "period": period,
        "renews": renew,
        "source": "file",
    }


def _walk(node: Any, out: list[dict[str, Any]]) -> None:  # noqa: ANN401 (any JSON or CSV value)
    """Every object that has a title and a date or a price; its children are not read again."""
    if len(out) >= ROWS_MAX:
        return
    if isinstance(node, list):
        for item in node:
            _walk(item, out)
        return
    if not isinstance(node, dict):
        return
    if _title(node) and any(
        _pick(node, names, skip) is not None
        for names, skip in ((WHEN, RENEW), (PRICE, ()), (STATE, ()), (RENEW, ()))
    ):
        out.append(node)
        return
    for value in node.values():
        _walk(value, out)


def _csv(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    # Bank exports often open with a few lines about the account before the header row.
    start = next(
        (i for i, line in enumerate(lines[:30]) if re.search(r"(?i)date", line)
         and re.search(r"(?i)amount|debit|price|total|description|title|item", line)),
        0,
    )  # fmt: skip
    body = "\n".join(lines[start:])
    try:
        dialect: Any = csv.Sniffer().sniff(body[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(body), dialect=dialect)
    return [row for _, row in zip(range(ROWS_MAX), reader, strict=False)]


def _one(path: str, data: bytes) -> list[dict[str, Any]]:
    store = _store(path)
    text = data.decode("utf-8-sig", "replace")
    if path.lower().endswith(".json"):
        try:
            parsed = json.loads(text)
        except ValueError:
            return []
        rows: list[dict[str, Any]] = []
        _walk(parsed, rows)
        bank = False
    elif path.lower().endswith(".csv"):
        rows = _csv(text)
        bank = store[0] == "bank"
    else:
        return []
    return [e for e in (_event(row, store, bank) for row in rows) if e is not None]


def read(name: str, data: bytes) -> list[dict[str, Any]]:
    """The events in one uploaded file. Raises ValueError with a plain reason."""
    if len(data) > BYTES_MAX:
        raise ValueError(
            "The file is larger than 30 MB. Pick only the Google Play part, or one statement."
        )
    low = name.lower()
    if low.endswith(".zip") or data[:2] == b"PK":
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as error:
            raise ValueError("The .zip file could not be opened.") from error
        events: list[dict[str, Any]] = []
        members = [m for m in archive.infolist() if m.filename.lower().endswith((".json", ".csv"))]
        total = 0
        for member in members[:FILES_MAX]:
            total += member.file_size
            if total > BYTES_MAX * 3:
                break
            events += _one(f"{name}/{member.filename}", archive.read(member))
    elif low.endswith((".json", ".csv")):
        events = _one(name, data)
    else:
        raise ValueError("Pick a .zip, .json or .csv file.")
    if not events:
        raise ValueError(
            "Nothing that looks like a purchase or a subscription was found in this file."
        )
    return events
