"""Update check and what's new (G.04).

Off until the user turns it on: a check is one GET to GitHub's public releases address for the app's
repository, and nothing else is sent. The answer says whether a newer version is out and shows its
release notes; nothing is downloaded or installed.
"""

import json
import re
from collections.abc import Callable
from typing import Any

from core import __version__
from core.apps import http_get

REPO = "Jacuzzik/hippocampus"
URL = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases"
NOTES_MAX = 6000

Get = Callable[[str, dict[str, str]], tuple[int, bytes]]


def _parts(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3]) or (0,)


def newer(latest: str, current: str = __version__) -> bool:
    return _parts(latest) > _parts(current)


def check(get: Get = http_get) -> dict[str, Any]:
    status, body = get(URL, {"Accept": "application/vnd.github+json", "User-Agent": "hippocampus"})
    base: dict[str, Any] = {"current": __version__, "page": PAGE}
    if status == 404:
        return {
            **base,
            "latest": "",
            "newer": False,
            "notes": "",
            "text": "No release is published yet.",
        }
    if status != 200:
        raise ValueError(f"GitHub answered {status}, so the check did not finish. Try again later.")
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError as error:
        raise ValueError("GitHub gave an answer that could not be read.") from error
    latest = str(data.get("tag_name") or data.get("name") or "")
    is_newer = bool(latest) and newer(latest)
    return {
        **base,
        "latest": latest,
        "newer": is_newer,
        "notes": str(data.get("body") or "")[:NOTES_MAX],
        "url": str(data.get("html_url") or PAGE),
        "published": str(data.get("published_at") or "")[:10],
        "text": f"Version {latest} is out." if is_newer else "You have the newest version.",
    }
