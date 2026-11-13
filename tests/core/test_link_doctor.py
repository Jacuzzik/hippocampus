from pathlib import Path

from core import link_doctor
from core.vault import open_index


def test_broken_links_and_lonely_notes_are_listed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("[[b]] and [[missing]]", encoding="utf-8")
    (vault / "b.md").write_text("plain", encoding="utf-8")
    (vault / "alone.md").write_text("[[alone]] links only to itself", encoding="utf-8")
    indexer = open_index(vault, tmp_path / "storage")
    indexer.full_sync()
    found = link_doctor.report(indexer.store)
    assert found["notes"] == 3
    assert found["broken"] == [{"note": "a.md", "link": "missing"}]
    assert found["broken_count"] == 1
    assert found["lonely"] == ["alone.md"] and found["lonely_count"] == 1


def test_a_vault_with_no_problems_gives_empty_lists(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("[[b]]", encoding="utf-8")
    (vault / "b.md").write_text("[[a]]", encoding="utf-8")
    indexer = open_index(vault, tmp_path / "storage")
    indexer.full_sync()
    found = link_doctor.report(indexer.store)
    assert found["broken"] == [] and found["lonely"] == []
