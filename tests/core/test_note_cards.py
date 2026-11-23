"""Note to card and card to note: a card keeps a link to its note, and gets its own note page."""

from pathlib import Path

import pytest

import core.__main__ as sidecar
from core.settings import Settings


def test_a_selection_becomes_a_card_and_the_card_gets_a_note(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Plan.md").write_text("# Plan\nShip the beta on Friday.\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "s", Settings(vault=vault))
    session.dispatch({"method": "open", "vault": str(vault)})
    card = session.dispatch(
        {"method": "card_from_note", "path": "Plan.md", "text": "Ship the beta on Friday."}
    )["card"]
    assert card["title"] == "Ship the beta on Friday."
    assert card["body"].endswith("From [[Plan]]") and card["source"] == "Plan.md"
    note = session.dispatch({"method": "card_note", "id": card["id"]})["note"]
    assert note.startswith("Cards/Ship the beta on Friday")
    assert "[[Plan]]" in (vault / note).read_text(encoding="utf-8")
    # Asked again, the same note page is updated, not a second one made.
    assert session.dispatch({"method": "card_note", "id": card["id"]})["note"] == note
    assert len(list((vault / "Cards").glob("*.md"))) == 1
    with pytest.raises(ValueError, match="Select some text"):
        session.dispatch({"method": "card_from_note", "path": "Plan.md", "text": "  "})
