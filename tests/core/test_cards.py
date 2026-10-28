from pathlib import Path

import pytest

from core.cards import CardStore


def test_created_card_survives_a_new_store(tmp_path: Path) -> None:
    store = CardStore(tmp_path / "cards")
    card = store.create("Notes", "12 notes", "assistant")
    assert CardStore(tmp_path / "cards").list() == [card]


def test_card_outlives_the_agent_that_made_it(tmp_path: Path) -> None:
    store = CardStore(tmp_path / "cards")
    card = store.create("Notes", "12 notes", "agent-gone")
    # The agent is removed: nothing deletes the card's file, and it still lists.
    assert store.list()[0]["created_by"] == "agent-gone"
    assert (tmp_path / "cards" / f"{card['id']}.json").is_file()


def test_locked_card_refuses_agent_changes(tmp_path: Path) -> None:
    store = CardStore(tmp_path / "cards")
    card = store.create("Notes", "12", "assistant")
    store.update(card["id"], {"locked": True}, by="owner")
    with pytest.raises(ValueError, match="locked"):
        store.update(card["id"], {"body": "13"}, by="agent")
    assert store.list()[0]["body"] == "12"


def test_owner_can_change_and_unlock(tmp_path: Path) -> None:
    store = CardStore(tmp_path / "cards")
    card = store.create("Notes", "12", "assistant")
    store.update(card["id"], {"locked": True}, by="owner")
    store.update(card["id"], {"body": "13"}, by="owner")
    store.update(card["id"], {"locked": False}, by="owner")
    assert store.list()[0]["locked"] is False
    assert store.list()[0]["body"] == "13"


def test_agent_cannot_lock(tmp_path: Path) -> None:
    store = CardStore(tmp_path / "cards")
    card = store.create("Notes", "12", "assistant")
    with pytest.raises(ValueError, match="owner"):
        store.update(card["id"], {"locked": True}, by="agent")


@pytest.mark.parametrize("title", ["", "   ", 3, "x" * 201])
def test_bad_title_is_refused(tmp_path: Path, title: object) -> None:
    with pytest.raises(ValueError):
        CardStore(tmp_path / "cards").create(title, "body", "owner")


def test_unknown_or_unsafe_id_is_refused(tmp_path: Path) -> None:
    store = CardStore(tmp_path / "cards")
    with pytest.raises(ValueError):
        store.update("../secret", {"body": "x"}, by="owner")
    with pytest.raises(ValueError):
        store.update("0" * 32, {"body": "x"}, by="owner")
