from pathlib import Path

import pytest

from core import safe_write
from core.__main__ import Session
from core.settings import Settings, load_settings


def session(tmp_path: Path) -> Session:
    path = tmp_path / "config" / "settings.toml"
    path.parent.mkdir()
    path.write_text('[network]\nmode = "ask"\n', encoding="utf-8")
    return Session(storage=tmp_path / "storage", settings=Settings(), settings_path=path)


def test_export_gives_the_settings_file_as_text(tmp_path: Path) -> None:
    assert session(tmp_path).settings_export()["text"] == '[network]\nmode = "ask"\n'


def test_import_replaces_the_file_and_the_settings_in_use(tmp_path: Path) -> None:
    one = session(tmp_path)
    answer = one.settings_import({"text": "[agents]\nshell = true\n"})
    assert answer["imported"] is True
    assert load_settings(one.settings_path).agent_shell is True
    assert one.settings.agent_shell is True


@pytest.mark.parametrize("text", ["not = [toml", '[network]\nmode = "everything"\n', "", 7])
def test_a_bad_import_is_refused_and_nothing_changes(tmp_path: Path, text: object) -> None:
    one = session(tmp_path)
    before = one.settings_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        one.settings_import({"text": text})
    assert one.settings_path.read_text(encoding="utf-8") == before
    assert list(one.settings_path.parent.iterdir()) == [one.settings_path]


def test_safe_write_replaces_the_file_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "state.json"
    safe_write.write_text(target, "one")
    safe_write.write_text(target, "two")
    assert target.read_text(encoding="utf-8") == "two"
    assert [file.name for file in target.parent.iterdir()] == ["state.json"]
