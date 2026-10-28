from pathlib import Path

import pytest

from core import __main__ as sidecar
from core.settings import Settings, load_settings, save_allowed_tools


def test_allowlist_round_trips_through_the_settings_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text('[vault]\npath = "brains/main"\n', encoding="utf-8")
    save_allowed_tools(("read_note", "search_notes"), path)
    loaded = load_settings(path)
    assert loaded.allowed_tools == ("read_note", "search_notes")
    assert loaded.vault is not None and loaded.vault.name == "main"  # other keys kept
    save_allowed_tools(None, path)
    assert load_settings(path).allowed_tools is None
    assert "allowed_tools" not in path.read_text(encoding="utf-8")


def test_bad_tool_names_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    with pytest.raises(ValueError, match="lowercase"):
        save_allowed_tools(('rm -rf"',), path)
    assert not path.exists()
    path.write_text('[ai]\nallowed_tools = "read_note"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="list of tool names"):
        load_settings(path)


def test_session_sets_and_lists_the_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "settings.toml"
    monkeypatch.setattr(sidecar, "SETTINGS_PATH", path)
    s = sidecar.Session(tmp_path, Settings(), emit=lambda event: None)
    assert s.dispatch({"method": "tools"}) == {"tools": [], "every": True}
    assert s.dispatch({"method": "set_tools", "names": ["read_note"]}) == {"names": ["read_note"]}
    assert s.settings.allowed_tools == ("read_note",)
    assert load_settings(path).allowed_tools == ("read_note",)
    assert s.dispatch({"method": "set_tools", "names": None}) == {"names": None}
    assert s.settings.allowed_tools is None


def test_session_refuses_a_bad_set_tools_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sidecar, "SETTINGS_PATH", tmp_path / "settings.toml")
    s = sidecar.Session(tmp_path, Settings(), emit=lambda event: None)
    with pytest.raises(ValueError, match="list of tool names"):
        s.dispatch({"method": "set_tools", "names": "read_note"})
    assert s.settings.allowed_tools is None
