"""Owner cards: small UI cards the main agent fills for the owner.

Each card is one JSON file in the app's storage folder, owned by the card. The file records
which agent made it, but it is never tied to that agent's life: removing an agent leaves its
cards in place. A locked card refuses changes from agents; only the owner can edit or unlock it.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

TITLE_MAX = 200
BODY_MAX = 10_000


class CardStore:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def list(self) -> list[dict[str, Any]]:
        if not self.folder.is_dir():
            return []
        cards = []
        for path in sorted(self.folder.glob("*.json")):
            try:
                cards.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                log.exception("skipping unreadable card file %s", path)
        return cards

    def create(self, title: object, body: object, by: object) -> dict[str, Any]:
        card = {
            "id": uuid.uuid4().hex,
            "title": _text(title, "title", TITLE_MAX),
            "body": _text(body, "body", BODY_MAX),
            "locked": False,
            "created_by": _text(by, "by", TITLE_MAX) if by else "owner",
        }
        self._write(card)
        return card

    def update(self, card_id: object, changes: dict[str, Any], by: object) -> dict[str, Any]:
        card = self._read(card_id)
        if "locked" in changes:
            if by != "owner":
                raise ValueError("only the owner can lock or unlock a card")
            if not isinstance(changes["locked"], bool):
                raise ValueError('"locked" must be true or false')
            card["locked"] = changes["locked"]
        elif card["locked"] and by != "owner":
            raise ValueError("the card is locked")
        if "title" in changes:
            card["title"] = _text(changes["title"], "title", TITLE_MAX)
        if "body" in changes:
            card["body"] = _text(changes["body"], "body", BODY_MAX)
        self._write(card)
        return card

    def _read(self, card_id: object) -> dict[str, Any]:
        if not isinstance(card_id, str) or not card_id.isalnum():
            raise ValueError('"id" must name a card')
        path = self.folder / f"{card_id}.json"
        if not path.is_file():
            raise ValueError(f"no card with id {card_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, card: dict[str, Any]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{card['id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(card, indent=2), encoding="utf-8")
        tmp.replace(path)


def _text(value: object, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'"{name}" needs a non-empty text')
    if len(value) > limit:
        raise ValueError(f'"{name}" is longer than {limit} characters')
    return value
