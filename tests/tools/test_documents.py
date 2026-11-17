"""Documents in the vault that are not notes (7.12): search and read text, CSV and PDF files."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tools import documents


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "v"
    (root / "docs").mkdir(parents=True)
    (root / ".hidden").mkdir()
    (root / "docs" / "plan.txt").write_text(
        "The launch is on Friday.\nBring the banner.", encoding="utf-8"
    )
    (root / "prices.csv").write_text("item,price\nvase,40\n", encoding="utf-8")
    (root / ".hidden" / "secret.txt").write_text("launch codes", encoding="utf-8")
    (root / "note.md").write_text("launch note", encoding="utf-8")
    return root.resolve()


def test_search_finds_text_and_csv_with_words_around_the_match(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    hits = documents.search(root, "LAUNCH")
    assert hits == ["docs/plan.txt: The launch is on Friday. Bring the banner."]
    assert documents.search(root, "prices") == ["prices.csv"]  # a name match
    with pytest.raises(ValueError, match="empty"):
        documents.search(root, "  ")


def test_read_refuses_notes_hidden_folders_and_paths_outside(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    assert documents.text_of(documents.inside(root, "prices.csv")).startswith("item,price")
    for bad in ("note.md", ".hidden/secret.txt", "../x.txt", "missing.txt"):
        with pytest.raises(ValueError):
            documents.inside(root, bad)


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs pdftotext")
def test_a_pdf_is_read_through_pdftotext(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path)
    pdf = root / "report.pdf"
    pdf.write_bytes(b"%PDF-fake")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=b"Quarterly revenue grew.", stderr=b"")

    monkeypatch.setattr(documents.subprocess, "run", fake_run)
    assert documents.search(root, "revenue") == ["report.pdf: Quarterly revenue grew."]
    documents.text_of(pdf)  # cached: no second run for the same file and time
    assert len(calls) == 1 and calls[0][1:3] == ["-l", str(documents.PDF_PAGES)]


def test_a_pdf_without_pdftotext_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path)
    (root / "a.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(documents.shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="pdftotext"):
        documents.text_of(root / "a.pdf")
