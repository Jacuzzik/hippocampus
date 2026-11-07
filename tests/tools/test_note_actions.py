import threading
from pathlib import Path

import pytest

from core import note_actions
from core.vault import Indexer
from tools.vault_tools import MAX_READ_CHARS


@pytest.fixture
def hub(vault: Path, indexer: Indexer) -> Indexer:
    # Projects is a group hub linking to beta; alpha is a plain note in a folder.
    (vault / "Projects.md").write_text("# Projects\n\n[[beta]]\n", encoding="utf-8")
    indexer.full_sync()
    return indexer


def test_group_is_the_hub_and_the_notes_it_links(
    hub: Indexer, vault: Path, lock: threading.RLock
) -> None:
    deleted = note_actions.delete(hub, lock, "Projects.md", "group")
    assert sorted(deleted) == ["Projects.md", "beta.md"]
    assert not (vault / "Projects.md").exists() and not (vault / "beta.md").exists()
    assert (vault / "projects" / "alpha.md").exists()


def test_hub_only_leaves_linked_notes_in_the_vault(
    hub: Indexer, vault: Path, lock: threading.RLock
) -> None:
    assert note_actions.delete(hub, lock, "Projects.md", "hub") == ["Projects.md"]
    assert not (vault / "Projects.md").exists() and (vault / "beta.md").exists()


def test_scopes_match_the_note_kind(hub: Indexer, lock: threading.RLock) -> None:
    with pytest.raises(ValueError):
        note_actions.delete(hub, lock, "Projects.md", "note")
    with pytest.raises(ValueError):
        note_actions.delete(hub, lock, "beta.md", "group")
    with pytest.raises(ValueError):
        note_actions.delete(hub, lock, "beta.md", "bogus")


def test_colour_group_sets_the_status_tag_on_every_note(
    hub: Indexer, vault: Path, lock: threading.RLock
) -> None:
    changed = note_actions.colour(hub, lock, "Projects.md", "group", "done")
    assert sorted(changed) == ["Projects.md", "beta.md"]
    assert "- done" in (vault / "beta.md").read_text(encoding="utf-8")


def test_colour_empty_status_clears_to_accent(
    hub: Indexer, vault: Path, lock: threading.RLock
) -> None:
    note_actions.colour(hub, lock, "beta.md", "note", "pending")
    assert note_actions.colour(hub, lock, "beta.md", "note", "") == ["beta.md"]
    assert "pending" not in (vault / "beta.md").read_text(encoding="utf-8")


def test_colour_rejects_an_unknown_status(hub: Indexer, lock: threading.RLock) -> None:
    with pytest.raises(ValueError):
        note_actions.colour(hub, lock, "beta.md", "note", "purple")


@pytest.mark.parametrize(
    "path", ["../secret.md", "projects/.hidden.md", "beta.txt", "missing.md", None]
)
def test_paths_must_be_existing_notes_in_the_vault(
    hub: Indexer, lock: threading.RLock, path: object
) -> None:
    with pytest.raises(ValueError):
        note_actions.delete(hub, lock, path, "note")


def test_read_full_returns_the_whole_note(hub: Indexer, vault: Path, lock: threading.RLock) -> None:
    long_text = "x" * (MAX_READ_CHARS + 500)
    (vault / "beta.md").write_text(long_text, encoding="utf-8")
    assert note_actions.read_full(hub, lock, "beta.md") == long_text


def test_welcome_and_test_hub_count_as_hubs_whatever_the_case(
    hub: Indexer, vault: Path, lock: threading.RLock
) -> None:
    # The vault holds Welcome.md and Test Hub.md; the hub list is in lower case in the app.
    (vault / "Welcome.md").write_text("# Welcome\n\n[[beta]]\n", encoding="utf-8")
    (vault / "Test Hub.md").write_text("# Test Hub\n\n[[alpha]]\n", encoding="utf-8")
    hub.full_sync()
    assert note_actions.delete(hub, lock, "Welcome.md", "hub") == ["Welcome.md"]
    assert not (vault / "Welcome.md").exists() and (vault / "beta.md").exists()
    changed = note_actions.colour(hub, lock, "Test Hub.md", "group", "done")
    assert sorted(changed) == ["Test Hub.md", "projects/alpha.md"]


def test_main_is_never_deleted_at_any_scope(
    hub: Indexer, vault: Path, lock: threading.RLock
) -> None:
    (vault / "MAIN.md").write_text("# Main\n\n[[beta]]\n", encoding="utf-8")
    hub.full_sync()
    for scope in ("note", "hub", "group"):
        with pytest.raises(ValueError, match="MAIN cannot be deleted"):
            note_actions.delete(hub, lock, "MAIN.md", scope)
    assert (vault / "MAIN.md").exists() and (vault / "beta.md").exists()


def test_notes_linked_from_main_cannot_be_deleted_through_a_group(
    hub: Indexer, vault: Path, lock: threading.RLock
) -> None:
    # Projects links beta; MAIN also links beta, so the group path must refuse and delete nothing.
    (vault / "MAIN.md").write_text("# Main\n\n[[beta]]\n", encoding="utf-8")
    hub.full_sync()
    with pytest.raises(ValueError, match="linked from MAIN"):
        note_actions.delete(hub, lock, "Projects.md", "group")
    with pytest.raises(ValueError, match="linked from MAIN"):
        note_actions.delete(hub, lock, "beta.md", "note")
    assert (vault / "Projects.md").exists() and (vault / "beta.md").exists()
    assert note_actions.delete(hub, lock, "Projects.md", "hub") == ["Projects.md"]
