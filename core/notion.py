"""Notion (D.07): read pages and databases into vault notes.

The user makes an internal integration at notion.so/my-integrations, shares the pages it may read
with it, and pastes its secret here. The secret goes to the system keychain. The app only reads:
it searches, reads a page's blocks or a database's rows, and writes them as a Markdown note under
the vault's "Notion" folder. Nothing in Notion is changed.
"""

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from core.apps import MAX_BYTES, SECONDS, _NoRedirect

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
FOLDER = "Notion"
BLOCKS_MAX = 1000
DEPTH_MAX = 3

Call = Callable[[str, str, str, dict[str, Any] | None], dict[str, Any]]


def check_token(token: object) -> str:
    value = str(token or "").strip()
    if not re.fullmatch(r"(secret_|ntn_)[A-Za-z0-9]{20,80}", value):
        raise ValueError(
            "Paste the integration's secret from notion.so/my-integrations (it starts with ntn_ or secret_)."
        )
    return value


def http_call(token: str, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(  # noqa: S310 (a fixed https address)
        f"{API}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with opener.open(request, timeout=SECONDS) as answer:
            raw = answer.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        try:
            reason = json.loads(error.read(4000)).get("message", "")
        except ValueError:
            reason = ""
        if error.code == 401:
            raise ValueError("Notion did not take the secret. Paste it again.") from error
        if error.code == 404:
            raise ValueError(
                "Notion cannot find that page. Share it with the integration first."
            ) from error
        raise ValueError(f"Notion answered {error.code}. {reason}".strip()) from error
    except OSError as error:
        raise ValueError("Notion could not be reached.") from error
    return json.loads(raw.decode("utf-8", "replace"))


def _plain(rich: object) -> str:
    return "".join(str(r.get("plain_text", "")) for r in rich or [] if isinstance(r, dict))


def title_of(item: dict[str, Any]) -> str:
    if item.get("object") == "database":
        return _plain(item.get("title")) or "Untitled database"
    for prop in (item.get("properties") or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _plain(prop.get("title")) or "Untitled"
    return "Untitled"


def search(token: str, query: str, call: Call = http_call) -> list[dict[str, str]]:
    found = call(token, "POST", "/search", {"query": query[:200], "page_size": 25})
    return [
        {
            "id": str(item.get("id", "")),
            "kind": str(item.get("object", "")),
            "title": title_of(item),
            "edited": str(item.get("last_edited_time", ""))[:10],
            "url": str(item.get("url", "")),
        }
        for item in found.get("results") or []
        if isinstance(item, dict)
    ]


LINE = {
    "paragraph": "{}",
    "heading_1": "# {}",
    "heading_2": "## {}",
    "heading_3": "### {}",
    "bulleted_list_item": "- {}",
    "numbered_list_item": "1. {}",
    "quote": "> {}",
    "callout": "> {}",
    "toggle": "- {}",
}


def _blocks(token: str, block: str, call: Call, depth: int, budget: list[int]) -> list[str]:
    lines: list[str] = []
    cursor = ""
    while budget[0] > 0:
        found = call(token, "GET", f"/blocks/{block}/children?page_size=100{cursor}", None)
        for item in found.get("results") or []:
            budget[0] -= 1
            kind = item.get("type", "")
            data = item.get(kind) or {}
            text = _plain(data.get("rich_text"))
            pad = "  " * depth
            if kind in LINE:
                lines.append(pad + LINE[kind].format(text))
            elif kind == "to_do":
                lines.append(f"{pad}- [{'x' if data.get('checked') else ' '}] {text}")
            elif kind == "code":
                lines += [f"{pad}```{data.get('language', '')}", text, f"{pad}```"]
            elif kind == "divider":
                lines.append("---")
            elif kind == "child_page":
                lines.append(f"{pad}- Page: {data.get('title', '')}")
            if item.get("has_children") and depth < DEPTH_MAX and kind != "child_page":
                lines += _blocks(token, str(item["id"]), call, depth + 1, budget)
        if not found.get("has_more"):
            break
        cursor = f"&start_cursor={found.get('next_cursor')}"
    return lines


def _cell(prop: dict[str, Any]) -> str:
    kind = prop.get("type", "")
    value = prop.get(kind)
    if kind in ("title", "rich_text"):
        return _plain(value)
    if kind in ("select", "status") and isinstance(value, dict):
        return str(value.get("name", ""))
    if kind == "multi_select":
        return ", ".join(str(v.get("name", "")) for v in value or [])
    if kind == "date" and isinstance(value, dict):
        return str(value.get("start", ""))
    if kind in ("number", "checkbox", "url", "email", "phone_number"):
        return "" if value is None else str(value)
    return ""


def page_markdown(token: str, item_id: str, call: Call = http_call) -> tuple[str, str]:
    """The note's title and Markdown for a page or a database."""
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", item_id):
        raise ValueError("That is not a Notion page id.")
    try:
        item = call(token, "GET", f"/pages/{item_id}", None)
    except ValueError:
        item = call(token, "GET", f"/databases/{item_id}", None)
    title = title_of(item)
    head = [f"# {title}", "", f"From Notion: {item.get('url', '')}", ""]
    if item.get("object") == "database":
        rows = (
            call(token, "POST", f"/databases/{item_id}/query", {"page_size": 100}).get("results")
            or []
        )
        names = list((rows[0].get("properties") or {}).keys()) if rows else []
        body = []
        if names:
            body = ["| " + " | ".join(names) + " |", "|" + " --- |" * len(names)]
            for row in rows:
                props = row.get("properties") or {}
                body.append(
                    "| "
                    + " | ".join(_cell(props.get(n) or {}).replace("|", "/") for n in names)
                    + " |"
                )
        else:
            body = ["No rows."]
        return title, "\n".join(head + body) + "\n"
    return title, "\n".join(head + _blocks(token, item_id, call, 0, [BLOCKS_MAX])) + "\n"


def note_path(title: str) -> str:
    safe = re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|#^\[\]]+', " ", title)).strip()[:80] or "Untitled"
    return f"{FOLDER}/{safe}.md"
