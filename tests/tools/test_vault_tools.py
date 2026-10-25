import threading
from pathlib import Path

import pytest

from core.vault import Indexer
from tools.vault_tools import vault_tools


@pytest.fixture
def tools(indexer: Indexer, lock: threading.RLock) -> dict:
    return vault_tools(indexer, lock)


def test_read_tools_are_read_tier(tools: dict) -> None:
    assert tools["search_notes"].tier == "read"
    assert tools["read_note"].tier == "read"
    assert tools["create_note"].tier == "write"


def test_search_matches_title_and_path(tools: dict) -> None:
    out = tools["search_notes"].run({"query": "alpha"})
    assert "projects/alpha.md: Alpha" in out
    assert tools["search_notes"].run({"query": "nothing-here"}) == "no notes match"


def test_read_note_returns_the_text(tools: dict) -> None:
    assert tools["read_note"].run({"path": "beta.md"}) == "# Beta\n"


@pytest.mark.parametrize("path", ["../secret.md", "/etc/passwd.md", "beta.txt", "", None])
def test_paths_must_stay_inside_the_vault(tools: dict, path: object) -> None:
    with pytest.raises(ValueError):
        tools["read_note"].run({"path": path})


def test_create_preview_shows_the_exact_change(tools: dict) -> None:
    preview = tools["create_note"].preview({"path": "new.md", "content": "hello\n"})
    assert "+++ b/new.md" in preview and "+hello" in preview


def test_create_note_writes_and_indexes(tools: dict, vault: Path, indexer: Indexer) -> None:
    assert tools["create_note"].run({"path": "notes/fresh.md", "content": "# Fresh\n"}) == (
        "created notes/fresh.md"
    )
    assert (vault / "notes" / "fresh.md").read_text(encoding="utf-8") == "# Fresh\n"
    assert indexer.store.search("fresh") == [("notes/fresh.md", "Fresh")]


def test_create_note_never_overwrites(tools: dict, vault: Path) -> None:
    with pytest.raises(FileExistsError):
        tools["create_note"].run({"path": "beta.md", "content": "replaced"})
    assert (vault / "beta.md").read_text(encoding="utf-8") == "# Beta\n"
