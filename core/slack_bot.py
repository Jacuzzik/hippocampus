"""Slack bot (7.25): a bot token the user pastes, kept in the keychain, answering in chosen channels and direct
messages, replying in threads, bridged to the agents' inboxes.

No listener is opened. The app asks Slack for new messages in the chosen conversations every few seconds (one
HTTPS request each) and posts replies the same way. A message becomes an inbox message to one agent whose `work` id
is `slack:<channel>:<ts>`; when that agent answers the user with the same `work`, the answer is posted in the
thread. Only the chosen conversations are read, and the bot never posts anywhere else."""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from core.apps import MAX_BYTES, SECONDS, _NoRedirect

API = "https://slack.com/api"
CHANNELS_MAX = 10
TEXT_MAX = 3000
WORK = re.compile(r"^slack:([CDG][A-Z0-9]{6,15}):(\d{9,11}\.\d{1,8})$")

Call = Callable[[str, str, dict[str, str]], dict[str, Any]]


def check_token(token: object) -> str:
    value = str(token or "").strip()
    if not re.fullmatch(r"xoxb-[A-Za-z0-9-]{20,200}", value):
        raise ValueError("Paste the bot token from api.slack.com/apps (it starts with xoxb-).")
    return value


def http_call(token: str, method: str, params: dict[str, str]) -> dict[str, Any]:
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(  # noqa: S310 (a fixed https address)
        f"{API}/{method}",
        data=urllib.parse.urlencode(params).encode(),
        headers={"Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with opener.open(request, timeout=SECONDS) as answer:
            data = json.loads(answer.read(MAX_BYTES + 1).decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        raise ValueError(f"Slack answered {error.code}.") from error
    except (OSError, ValueError) as error:
        raise ValueError("Slack could not be reached.") from error
    if not isinstance(data, dict) or not data.get("ok"):
        reason = str(data.get("error", "an error")) if isinstance(data, dict) else "an error"
        if reason in ("invalid_auth", "not_authed", "token_revoked", "account_inactive"):
            raise ValueError("Slack did not take the token. Paste it again.")
        if reason == "missing_scope":
            raise ValueError(
                f"The bot is missing a permission ({data.get('needed', 'a scope')}). "
                "Add it under OAuth and Permissions in the Slack app, then reinstall the app."
            )
        raise ValueError(f"Slack said: {reason}.")
    return data


def identify(token: str, call: Call = http_call) -> dict[str, str]:
    found = call(token, "auth.test", {})
    return {
        "team": str(found.get("team", "")),
        "bot": str(found.get("user", "")),
        "bot_id": str(found.get("user_id", "")),
    }


def conversations(token: str, call: Call = http_call) -> list[dict[str, str]]:
    """The channels the bot is in and its direct messages, for the user to choose from."""
    found = call(
        token,
        "users.conversations",
        {"types": "public_channel,private_channel,im", "limit": "200", "exclude_archived": "true"},
    )
    rows = []
    for item in found.get("channels") or []:
        if not isinstance(item, dict) or not WORK.match(f"slack:{item.get('id')}:1700000000.0"):
            continue
        if item.get("is_im"):
            rows.append(
                {
                    "id": str(item["id"]),
                    "name": f"Direct message ({item.get('user', '?')})",
                    "kind": "dm",
                }
            )
        else:
            rows.append(
                {"id": str(item["id"]), "name": f"#{item.get('name', '?')}", "kind": "channel"}
            )
    return rows


def _clean(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:TEXT_MAX]


def fetch_new(
    token: str,
    chosen: dict[str, str],
    bot_id: str,
    call: Call = http_call,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """New human messages in the chosen conversations, oldest first, and the updated newest-seen stamps."""
    found: list[dict[str, str]] = []
    seen = dict(chosen)
    for channel, last in list(chosen.items())[:CHANNELS_MAX]:
        data = call(
            token, "conversations.history", {"channel": channel, "oldest": last, "limit": "20"}
        )
        for message in sorted(data.get("messages") or [], key=lambda m: float(m.get("ts", 0))):
            ts = str(message.get("ts", ""))
            if not ts or float(ts) <= float(seen[channel]):
                continue
            seen[channel] = ts
            if message.get("bot_id") or message.get("subtype") or message.get("user") == bot_id:
                continue
            text = _clean(message.get("text"))
            if text:
                found.append(
                    {
                        "channel": channel,
                        "ts": str(message.get("thread_ts") or ts),
                        "user": str(message.get("user", "")),
                        "text": text,
                    }
                )
    return found, seen


def reply(token: str, work: str, text: str, chosen: set[str], call: Call = http_call) -> None:
    """Post `text` in the thread a `slack:<channel>:<ts>` work id names, only in a chosen conversation."""
    parsed = WORK.match(work)
    if not parsed or parsed.group(1) not in chosen:
        raise ValueError("That Slack thread is not one of the chosen conversations.")
    call(
        token,
        "chat.postMessage",
        {
            "channel": parsed.group(1),
            "thread_ts": parsed.group(2),
            "text": _clean(text) or "(no text)",
        },
    )


def now_stamp() -> str:
    return f"{time.time():.6f}"
