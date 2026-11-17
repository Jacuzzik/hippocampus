"""The Add agent dialog can show the briefing before the agent exists."""

from pathlib import Path

from core.__main__ import Session
from core.settings import Settings


def _session(tmp_path: Path) -> Session:
    return Session(
        storage=tmp_path / "storage",
        settings=Settings(),
        settings_path=tmp_path / "settings.toml",
    )


def test_preview_fills_in_the_typed_words_and_saves_nothing(tmp_path: Path) -> None:
    session = _session(tmp_path)
    found = session.briefing_preview(
        {
            "name": "Ada",
            "description": "Sorts the inbox",
            "goal": "Empty inbox daily",
            "folder": "/w/IT",
        }
    )
    text = found["text"]
    assert text.startswith("1. Role\nYou are Ada (")
    assert "Sorts the inbox" in text and "Empty inbox daily" in text and "/w/IT" in text
    assert found["characters"] == len(text)
    assert "{" not in text.split("Example:")[0]  # no blank left unfilled before the JSON example
    assert not (tmp_path / "storage" / "briefings").exists()


def test_preview_copes_with_missing_and_wrong_typed_fields(tmp_path: Path) -> None:
    text = _session(tmp_path).briefing_preview({"name": 7, "goal": None})["text"]
    assert "You are New agent (" in text and "not described yet" in text
