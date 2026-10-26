from pathlib import Path

import pytest

from core.__main__ import Session, handle


@pytest.fixture
def session(sample_vault: tuple[Path, object], storage: Path) -> Session:
    vault, _ = sample_vault
    opened = Session(storage)
    opened.open(vault)
    yield opened
    opened.close()


def test_read_returns_the_note_text(session: Session, sample_vault: tuple[Path, object]) -> None:
    vault, _ = sample_vault
    note = session.graph()["nodes"][0]["id"]
    answer = handle(session, f'{{"id": 7, "method": "read", "path": "{note}"}}')
    assert answer == {"id": 7, "result": {"id": note, "text": (vault / note).read_text("utf-8")}}


@pytest.mark.parametrize("path", ["../secret.md", "/etc/passwd.md", "beta.txt"])
def test_read_refuses_paths_outside_the_vault(session: Session, path: str) -> None:
    answer = handle(session, f'{{"id": 8, "method": "read", "path": "{path}"}}')
    assert "error" in answer and "result" not in answer


def test_read_needs_an_open_vault(storage: Path) -> None:
    answer = handle(Session(storage), '{"id": 9, "method": "read", "path": "beta.md"}')
    assert answer["error"] == "no vault is open"
