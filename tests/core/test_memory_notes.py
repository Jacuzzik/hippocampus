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
