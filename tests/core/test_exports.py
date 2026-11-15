"""Exports: a picture of the graph and a zip of the notes land in the exports folder; the vault is never changed."""

import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

import core.__main__ as sidecar
from core import exports
from core.settings import Settings


def test_a_text_is_saved_under_a_dated_name_in_the_exports_folder(tmp_path: Path) -> None:
    path = exports.save_text(tmp_path, "graph.svg", "<svg></svg>")
    assert path.parent == tmp_path / "exports"
    assert path.name.endswith("-graph.svg")
    assert path.read_text(encoding="utf-8") == "<svg></svg>"


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("../graph.svg", "<svg/>"),
        ("graph.exe", "<svg/>"),
        ("Graph.svg", "<svg/>"),
        ("/etc/passwd", "x"),
        ("graph.svg", ""),
        ("graph.svg", "x" * (exports.MAX_TEXT + 1)),
        (None, "x"),
    ],
)
def test_a_bad_name_or_text_is_refused_and_nothing_is_written(
    tmp_path: Path, name: object, text: object
) -> None:
    with pytest.raises(ValueError):
        exports.save_text(tmp_path, name, text)
    assert not (tmp_path / "exports").exists()


def test_the_notes_are_zipped_and_the_vault_is_left_as_it_was(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "ideas").mkdir(parents=True)
    (vault / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    (vault / "ideas" / "beta.md").write_text("# Beta\n", encoding="utf-8")
    (vault / "picture.png").write_bytes(b"png")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "hidden.md").write_text("no", encoding="utf-8")
    before = sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*"))
    storage = tmp_path / "storage"
    session = sidecar.Session(storage, replace(Settings(), vault=vault), emit=lambda e: None)
    done = session.dispatch({"method": "export_notes"})
    assert done["notes"] == 2
    with zipfile.ZipFile(done["path"]) as found:
        assert sorted(found.namelist()) == ["alpha.md", "ideas/beta.md"]
        assert found.read("ideas/beta.md") == b"# Beta\n"
    assert sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*")) == before


def test_exporting_with_no_vault_or_no_notes_says_why(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path / "s", Settings(), emit=lambda e: None)
    with pytest.raises(ValueError, match="no vault is open"):
        session.dispatch({"method": "export_notes"})
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no notes"):
        exports.zip_notes(tmp_path / "s", empty)


def test_the_graph_picture_is_saved_through_the_call(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    done = session.dispatch({"method": "save_export", "name": "graph.svg", "text": "<svg/>"})
    assert Path(done["path"]).read_text(encoding="utf-8") == "<svg/>"
