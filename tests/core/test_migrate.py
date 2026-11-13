from datetime import datetime
from pathlib import Path

import pytest

from core import migrate


def test_a_new_empty_folder_starts_at_the_current_version_with_no_backup(tmp_path: Path) -> None:
    storage = tmp_path / "data" / "storage"
    assert migrate.migrate(storage) is None
    assert migrate.read_version(storage) == migrate.CURRENT
    assert not (tmp_path / "data" / "backups").exists()


def test_a_folder_from_before_versions_is_copied_to_backups_first(tmp_path: Path) -> None:
    storage = tmp_path / "data" / "storage"
    storage.mkdir(parents=True)
    (storage / "chat_history.json").write_text('{"keep": 1}', encoding="utf-8")
    (storage / "index").mkdir()
    (storage / "index" / "big.sqlite3").write_text("rebuilt anyway", encoding="utf-8")
    saved = migrate.migrate(storage)
    assert saved is not None and saved.parent == tmp_path / "data" / "backups"
    assert (saved / "chat_history.json").read_text(encoding="utf-8") == '{"keep": 1}'
    assert not (saved / "index").exists()
    assert (storage / "chat_history.json").read_text(encoding="utf-8") == '{"keep": 1}'
    assert migrate.read_version(storage) == migrate.CURRENT


def test_a_folder_at_the_current_version_is_left_alone(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    migrate.migrate(storage)
    (storage / "usage.jsonl").write_text("x", encoding="utf-8")
    assert migrate.migrate(storage) is None
    assert not (tmp_path / "backups").exists()


def test_a_folder_from_a_newer_app_is_refused_and_untouched(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "data_version").write_text("99\n", encoding="utf-8")
    (storage / "usage.jsonl").write_text("x", encoding="utf-8")
    with pytest.raises(migrate.NewerData, match="newer version"):
        migrate.migrate(storage)
    assert (storage / "usage.jsonl").read_text(encoding="utf-8") == "x"
    assert not (tmp_path / "backups").exists()


def test_a_later_step_runs_after_the_backup_and_the_version_is_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = tmp_path / "storage"
    migrate.migrate(storage)
    (storage / "old.txt").write_text("old", encoding="utf-8")
    monkeypatch.setattr(migrate, "CURRENT", 2)
    seen: list[str] = []

    def step(folder: Path) -> None:
        # The backup already holds the file this step is about to remove.
        seen.append(next((tmp_path / "backups").iterdir()).joinpath("old.txt").read_text())
        (folder / "old.txt").unlink()

    monkeypatch.setitem(migrate.STEPS, 1, step)
    saved = migrate.migrate(storage)
    assert seen == ["old"]
    assert saved is not None and (saved / "old.txt").exists()
    assert not (storage / "old.txt").exists()
    assert migrate.read_version(storage) == 2


def test_backup_names_carry_the_old_version_and_the_time(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    saved = migrate.backup(storage, 3, datetime(2026, 11, 13, 10, 30, 5))
    assert saved.name == "storage-v3-20261113-103005"


def test_two_backups_in_one_second_do_not_collide(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "a.txt").write_text("a", encoding="utf-8")
    when = datetime(2026, 11, 13, 10, 30, 5)
    first, second = migrate.backup(storage, 0, when), migrate.backup(storage, 0, when)
    assert first != second and (second / "a.txt").exists()
