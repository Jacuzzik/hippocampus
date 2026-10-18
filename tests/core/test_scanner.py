import logging
from pathlib import Path

import pytest

from core.vault import scanner
from core.vault.scanner import iter_notes, read_note, stat_note


def write(root: Path, rel: str, text: str = "x") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def paths(root: Path) -> list[str]:
    return [note.path for note in iter_notes(root)]


def test_finds_markdown_recursively_in_sorted_order(tmp_path: Path) -> None:
    for rel in ("b.md", "a.md", "sub/c.md", "sub/deeper/d.MD", "notes.txt", "e.md.bak"):
        write(tmp_path, rel)
    assert paths(tmp_path) == ["a.md", "b.md", "sub/c.md", "sub/deeper/d.MD"]


def test_skips_hidden_files_and_folders(tmp_path: Path) -> None:
    for rel in (".obsidian/workspace.md", ".git/x.md", ".trash/old.md", "a/.hidden.md", "ok.md"):
        write(tmp_path, rel)
    assert paths(tmp_path) == ["ok.md"]


def test_reports_stat_fields(tmp_path: Path) -> None:
    path = write(tmp_path, "a.md", "hello")
    (note,) = iter_notes(tmp_path)
    assert note.size == 5
    assert note.mtime_ns == path.stat().st_mtime_ns
    assert note.abs_path == path


def test_symlink_outside_vault_is_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    vault, outside = tmp_path / "vault", tmp_path / "outside"
    write(outside, "secret.md")
    write(vault, "real.md")
    (vault / "escape.md").symlink_to(outside / "secret.md")
    (vault / "inside.md").symlink_to(vault / "real.md")
    (vault / "linked_dir").symlink_to(outside, target_is_directory=True)
    with caplog.at_level(logging.WARNING, logger="hippocampus.core.vault"):
        assert paths(vault) == ["inside.md", "real.md"]
    assert "escape.md" in caplog.text


def test_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(scanner, "MAX_NOTE_BYTES", 10)
    write(tmp_path, "small.md", "0123456789")
    write(tmp_path, "big.md", "0123456789!")
    with caplog.at_level(logging.WARNING, logger="hippocampus.core.vault"):
        assert paths(tmp_path) == ["small.md"]
    assert "big.md" in caplog.text


def test_stat_note_rejects_paths_outside_and_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    write(vault, ".obsidian/x.md")
    other = write(tmp_path, "other.md")
    assert stat_note(vault, other) is None
    assert stat_note(vault, vault / ".obsidian/x.md") is None
    assert stat_note(vault, vault / "missing.md") is None
    (vault / "folder.md").mkdir()
    assert stat_note(vault, vault / "folder.md") is None


def test_non_utf8_is_logged_and_replaced(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "latin1.md").write_bytes("caf\xe9 [[Link]]".encode("latin-1"))
    (note,) = iter_notes(tmp_path)
    with caplog.at_level(logging.WARNING, logger="hippocampus.core.vault"):
        result = read_note(note)
    assert result is not None
    data, text = result
    assert data == "caf\xe9 [[Link]]".encode("latin-1")
    assert text == "caf� [[Link]]"
    assert "latin1.md" in caplog.text


def test_read_vanished_file_returns_none(tmp_path: Path) -> None:
    path = write(tmp_path, "gone.md")
    (note,) = iter_notes(tmp_path)
    path.unlink()
    assert read_note(note) is None
