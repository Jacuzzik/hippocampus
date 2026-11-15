"""The memory list also says the size cap, so the window can draw a meter."""

from pathlib import Path

import pytest

from core.__main__ import Session
from core.settings import Settings


def test_memory_list_carries_the_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hive = tmp_path / "hive"
    (hive / "agents" / "kevin").mkdir(parents=True)
    (hive / "agents" / "kevin" / "memory.md").write_text("x" * 100)
    monkeypatch.setenv("MD_HIVE_DIR", str(hive))
    session = Session(
        storage=tmp_path / "storage",
        settings=Settings(memory_max_bytes=5000),
        settings_path=tmp_path / "settings.toml",
    )
    found = session.memory_notes()
    assert found["max_bytes"] == 5000
    assert found["notes"][0]["agent"] == "kevin"
    assert found["notes"][0]["bytes"] == 100


def test_note_counts_tell_rules_from_notes_and_find_repeats() -> None:
    from core.session_memory import note_counts

    text = "\n".join(
        [
            "# Memory",
            "## Rules (never moved)",
            "- Always run the tests",
            "- Never print a key",
            "## Notes",
            "- The vault lives in Documents",
            "- the  vault lives in documents",
            "plain text is not counted",
            "- ",
        ]
    )
    assert note_counts(text) == {"rules": 2, "notes": 2, "repeated": 1}


def test_memory_list_carries_the_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hive = tmp_path / "hive"
    (hive / "agents" / "pam").mkdir(parents=True)
    (hive / "agents" / "pam" / "memory.md").write_text("## Rules\n- one\n## Notes\n- two\n- two\n")
    monkeypatch.setenv("MD_HIVE_DIR", str(hive))
    session = Session(
        storage=tmp_path / "storage",
        settings=Settings(),
        settings_path=tmp_path / "settings.toml",
    )
    row = session.memory_notes()["notes"][0]
    assert (row["rules"], row["notes"], row["repeated"]) == (1, 2, 1)
