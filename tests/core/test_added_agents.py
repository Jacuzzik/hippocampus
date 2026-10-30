from pathlib import Path

import pytest

from core import __main__ as sidecar
from core.added_agents import load, save
from core.settings import Settings

AGENT = {"id": "a1", "name": "Janvy", "provider": "claude", "model": "m", "folder": "/x"}


def test_saved_agents_survive_a_new_session(tmp_path: Path) -> None:
    first = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    first.save_agents({"agents": [AGENT]})
    second = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    assert second.agents_state() == {"agents": [AGENT]}


def test_no_file_lists_no_agents(tmp_path: Path) -> None:
    assert load(tmp_path / "agents.json") == []


def test_save_rejects_a_list_without_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be a list"):
        save(tmp_path / "agents.json", [{"name": "no id"}])
    assert not (tmp_path / "agents.json").exists()


def test_save_rejects_a_non_list(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    with pytest.raises(ValueError, match="must be a list"):
        session.save_agents({"agents": None})
