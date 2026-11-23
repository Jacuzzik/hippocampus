"""One search box: notes by title and text, messages, tasks, events and agents, every word matching."""

from pathlib import Path

import core.__main__ as sidecar
from core import added_agents, calendar_board, inbox, search_all
from core.settings import Settings


def test_every_group_matches_every_word() -> None:
    found = search_all.everything(
        "release plan",
        [],
        [
            {
                "id": "m1",
                "from": "ada",
                "to": "user",
                "subject": "Release",
                "body": "the plan is set",
            }
        ],
        [{"id": "K-1", "title": "Release plan", "status": "doing"}],
        [{"id": "e1", "date": "2026-11-24", "title": "Release plan review"}],
        [{"id": "ada", "name": "Ada", "description": "release plan owner"}],
    )
    assert [m["id"] for m in found["messages"]] == ["m1"]
    assert found["messages"][0]["snippet"].startswith("the plan")
    assert [t["id"] for t in found["tasks"]] == ["K-1"]
    assert [e["id"] for e in found["events"]] == ["e1"]
    assert [a["id"] for a in found["agents"]] == ["ada"]
    assert search_all.everything("", [], [], [], [], [])["notes"] == []


def test_a_short_query_never_reads_note_text(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("zebra crossing", encoding="utf-8")
    assert search_all.notes("ze", [], tmp_path, ["a.md"]) == []
    rows = search_all.notes("zebra", [], tmp_path, ["a.md"])
    assert rows[0]["path"] == "a.md" and "zebra" in rows[0]["snippet"]


def test_the_call_searches_the_open_vault_and_the_rest(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Plans.md").write_text("# Plans\n", encoding="utf-8")
    (vault / "b.md").write_text("# B\nThe launch plans are here.\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "s", Settings(vault=vault))
    session.dispatch({"method": "open", "vault": str(vault)})
    added_agents.save(session.agents_path, [{"id": "pam", "name": "Pam Plans"}])
    inbox.send(session.hive_path, "pam", inbox.USER, "Plans", "Here are the plans.")
    calendar_board.add(
        session.events_path, "2026-11-24", "10:00", "Plans review", "", "hippoherman"
    )
    found = session.dispatch({"method": "search_all", "query": "plans"})
    assert [n["path"] for n in found["notes"]] == ["Plans.md", "b.md"]
    assert found["messages"][0]["subject"] == "Plans"
    assert found["events"][0]["title"] == "Plans review"
    assert found["agents"][0]["id"] == "pam"
