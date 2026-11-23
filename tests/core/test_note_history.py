"""Note history: a copy before each editing session, the last 20 kept, and a restore that can be undone."""

from pathlib import Path

import pytest

import core.__main__ as sidecar
from core import note_history
from core.settings import Settings

T = 1_800_000_000  # a time in seconds, so version ids have 13 digits


def test_one_copy_per_editing_session_and_only_the_last_20_kept(tmp_path: Path) -> None:
    assert note_history.keep(tmp_path, "a.md", "one", now=T + 1000)
    assert not note_history.keep(tmp_path, "a.md", "two", now=T + 1010)  # same session
    assert not note_history.keep(tmp_path, "a.md", "one", now=T + 2000)  # same text as the newest
    for i in range(25):
        assert note_history.keep(tmp_path, "a.md", f"v{i}", now=T + 3000 + i * 400)
    found = note_history.versions(tmp_path, "a.md")
    assert len(found) == note_history.KEEP
    assert found[0]["first"] == "v24"
    assert note_history.versions(tmp_path, "b.md") == []


def test_a_version_id_must_be_a_time_so_no_path_can_be_read(tmp_path: Path) -> None:
    note_history.keep(tmp_path, "a.md", "one", now=T + 1000)
    with pytest.raises(ValueError, match="not a version"):
        note_history.text_of(tmp_path, "a.md", "../../etc/passwd")
    with pytest.raises(ValueError, match="no longer kept"):
        note_history.text_of(tmp_path, "a.md", "9999999999999")


def test_saving_keeps_the_old_text_and_restoring_puts_it_back(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# A\nfirst\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "s", Settings(vault=vault))
    session.dispatch({"method": "open", "vault": str(vault)})
    session.dispatch({"method": "note_save", "path": "a.md", "text": "# A\nsecond\n"})
    versions = session.dispatch({"method": "note_history", "path": "a.md"})["versions"]
    assert len(versions) == 1
    version = versions[0]["id"]
    shown = session.dispatch({"method": "note_version", "path": "a.md", "version": version})
    assert shown["text"] == "# A\nfirst\n"
    session.dispatch({"method": "note_restore", "path": "a.md", "version": version})
    assert (vault / "a.md").read_text(encoding="utf-8") == "# A\nfirst\n"
    # The text the restore replaced is kept too, so the restore can be undone.
    texts = [
        session.dispatch({"method": "note_version", "path": "a.md", "version": v["id"]})["text"]
        for v in session.dispatch({"method": "note_history", "path": "a.md"})["versions"]
    ]
    assert "# A\nsecond\n" in texts
    with pytest.raises(ValueError):
        session.dispatch({"method": "note_history", "path": "../outside.md"})
