"""Tests for the control panel backend: network, budgets, activity, memory, jobs, helpers, keys."""

import json
import threading
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ai import network
from ai.providers import base
from ai.providers.base import NetworkBlocked, Reply
from ai.router import Router
from core import __main__ as sidecar
from core import activity, budget, helpers, jobs, memory, share, skills
from core.memory import NotSetUp
from core.settings import Caps, Settings, load_settings, save_budget, save_network_mode

NOW = datetime(2026, 10, 27, 12, 0).astimezone()


class Scripted:
    name = "scripted"

    def __init__(self, *replies: Reply) -> None:
        self.replies = list(replies)

    async def chat(self, messages: list[dict[str, Any]], tools: list[Any]) -> Reply:
        return self.replies.pop(0)


def chat(session: sidecar.Session, text: str, **extra: object) -> dict[str, Any]:
    return session.chat({"chat": 1, "text": text, **extra})


# --- network -----------------------------------------------------------------------------


def test_off_blocks_a_model_call_before_anything_leaves(monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("urlopen was called while the network is off")

    monkeypatch.setattr(urllib.request, "urlopen", must_not_run)
    network.set_mode("off")
    with pytest.raises(NetworkBlocked, match="network is Off"):
        base._post("https://api.anthropic.com/v1/messages", {}, {}, 1.0)
    network.set_mode("listen")
    with pytest.raises(NetworkBlocked, match="network is Listen"):
        base._post("https://api.anthropic.com/v1/messages", {}, {}, 1.0)


def test_only_converse_and_open_allow_model_calls() -> None:
    for mode, allowed in [("off", False), ("listen", False), ("converse", True), ("open", True)]:
        network.set_mode(mode)
        assert network.allows_model_calls() is allowed, mode
    with pytest.raises(ValueError):
        network.set_mode("everywhere")


def test_network_mode_defaults_to_off_and_is_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "settings.toml"
    path.write_text('settings_version = 1\n\n[ai]\nprovider = "claude"\n', encoding="utf-8")
    assert load_settings(path).network_mode == "off"
    monkeypatch.setattr(sidecar, "SETTINGS_PATH", path)
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    assert session.dispatch({"method": "set_network", "mode": "converse"}) == {
        "mode": "converse",
        "modes": ["off", "listen", "converse", "open"],
    }
    assert network.mode() == "converse"
    assert load_settings(path).network_mode == "converse"
    assert 'provider = "claude"' in path.read_text(encoding="utf-8")  # the rest of the file is kept
    with pytest.raises(ValueError):
        save_network_mode("sideways", path)


# --- budgets -----------------------------------------------------------------------------


def test_a_tiny_cap_pauses_the_next_request_and_allowance_lets_one_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = Scripted(Reply("first", tokens=50), Reply("second", tokens=50))
    monkeypatch.setattr(sidecar, "build_router", lambda settings, key: Router(None, provider))
    session = sidecar.Session(tmp_path, Settings(assistant_budget=Caps(daily=10)))
    assert chat(session, "one") == {"reply": "first", "stopped": False}

    paused = chat(session, "two")
    assert paused["budget"] == {"scope": "assistant", "window": "daily", "used": 50, "cap": 10}
    assert paused["reply"] == ""

    session.dispatch({"method": "budget_allow"})
    assert chat(session, "two") == {"reply": "second", "stopped": False}
    assert chat(session, "three").get("budget") is not None  # the allowance was for one request


def test_budget_windows_and_scopes(tmp_path: Path) -> None:
    ledger = budget.Ledger(tmp_path / "usage.jsonl")
    ledger.add("assistant", 30, now=NOW - timedelta(days=1))  # yesterday
    ledger.add("helper", 40, now=NOW)
    assert ledger.used("daily", NOW) == 40
    assert ledger.used("weekly", NOW) >= 40
    assert ledger.used("daily", NOW, agent="assistant") == 0
    over = ledger.first_overrun({"app": (Caps(weekly=50), None)}, NOW)
    assert over is None or over.used >= 50
    assert ledger.first_overrun({"app": (Caps(monthly=60), None)}, NOW) == budget.Overrun(
        "app", "monthly", 70, 60
    )


def test_five_hour_window_is_rolling(tmp_path: Path) -> None:
    ledger = budget.Ledger(tmp_path / "usage.jsonl")
    ledger.add("app", 30, now=NOW - timedelta(hours=3))  # inside the last 5 hours
    ledger.add("app", 70, now=NOW - timedelta(hours=6))  # outside it
    assert ledger.used("five_hour", NOW) == 30
    assert ledger.first_overrun({"app": (Caps(five_hour=30), None)}, NOW) == budget.Overrun(
        "app", "five_hour", 30, 30
    )


def test_budget_caps_are_saved_and_read_back(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text('settings_version = 1\n\n[budget]\ndaily = 5\n\n[ai]\nprovider = "claude"\n')
    save_budget(Caps(five_hour=40, daily=100, weekly=500), Caps(daily=20), path)
    loaded = load_settings(path)
    assert loaded.budget == Caps(five_hour=40, daily=100, weekly=500, monthly=0)
    assert loaded.assistant_budget == Caps(daily=20)
    assert path.read_text(encoding="utf-8").count("[budget]") == 1


# --- activity log ------------------------------------------------------------------------


def test_approvals_and_outcomes_are_logged_without_note_text(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session.journal_event(
        {
            "event": "tool",
            "call": "card-1",
            "name": "create_note",
            "tier": "write",
            "status": "running",
        }
    )
    session.journal_event(
        {
            "event": "tool",
            "call": "card-1",
            "name": "create_note",
            "tier": "write",
            "status": "done",
        }
    )
    session.journal_event(
        {
            "event": "tool",
            "call": "card-2",
            "name": "create_note",
            "tier": "write",
            "status": "declined",
        }
    )
    session.journal_event(
        {"event": "tool", "name": "read_note", "tier": "read", "status": "running"}
    )
    rows = session.dispatch({"method": "activity", "limit": 50})["rows"]
    assert [r["kind"] for r in rows] == ["approval", "tool", "approval"]
    assert [r["approved"] for r in rows if r["kind"] == "approval"] == [False, True]
    assert [r["call"] for r in rows if r["kind"] == "approval"] == ["card-2", "card-1"]
    assert all("preview" not in r and "diff" not in json.dumps(r) for r in rows)
    only = session.dispatch({"method": "activity", "kind": "approval"})["rows"]
    assert len(only) == 2
    with pytest.raises(ValueError):
        session.dispatch({"method": "activity", "kind": "gossip"})


def test_errors_reach_the_log(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    answer = sidecar.handle(session, json.dumps({"id": 1, "method": "nope"}))
    assert "unknown method" in answer["error"]
    assert activity.read(tmp_path, "error")[0]["method"] == "nope"


# --- ask me queue -------------------------------------------------------------------------


def test_waiting_questions_are_listed_and_answering_clears_them(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session.asks.open("q1", "Which folder?")
    assert session.dispatch({"method": "asks"}) == {
        "asks": [{"call": "q1", "question": "Which folder?"}]
    }
    session.dispatch({"method": "answer", "call": "q1", "text": "notes"})
    assert session.dispatch({"method": "asks"}) == {"asks": []}
    with pytest.raises(ValueError):
        session.dispatch({"method": "answer", "call": "q1", "text": "again"})


# --- memory ------------------------------------------------------------------------------

MEMORY = """---
created_by: assistant
---
# Log

## Week 1
{a}
## Week 2
{b}
## Week 3
{c}
"""


def test_long_memory_moves_its_oldest_sections_to_an_archive(tmp_path: Path) -> None:
    note = tmp_path / "log.md"
    note.write_text(MEMORY.format(a="x" * 300, b="y" * 300, c="z" * 10), encoding="utf-8")
    archive = memory.trim_memory_file(tmp_path, note, limit=400)
    assert archive == tmp_path / "log-archive.md"
    kept = note.read_text(encoding="utf-8")
    assert "## Week 3" in kept and "## Week 1" not in kept
    assert "[[log-archive]]" in kept and kept.count("[[log-archive]]") == 1
    assert "## Week 1" in archive.read_text(encoding="utf-8")
    assert memory.trim_memory_file(tmp_path, note, limit=400) is None  # already under the limit
    assert memory.trim_memory_file(tmp_path, archive, limit=10) is None  # archives are not trimmed


def test_short_or_non_memory_notes_are_left_alone(tmp_path: Path) -> None:
    short = tmp_path / "short.md"
    short.write_text(MEMORY.format(a="a", b="b", c="c"), encoding="utf-8")
    assert memory.trim_memory_file(tmp_path, short, limit=10_000) is None
    plain = tmp_path / "plain.md"
    plain.write_text("# Plain\n\n## A\n" + "x" * 900 + "\n## B\n", encoding="utf-8")
    assert memory.trim_memory_file(tmp_path, plain, limit=100) is None  # not a memory note
    assert memory.is_memory("---\ncreated_by: assistant\n---\nhi")
    assert not memory.is_memory("---\ncreated_by: you\n---\nhi")


def test_opening_a_vault_trims_long_memory_notes(tmp_path: Path) -> None:
    vault = tmp_path / "brain"
    vault.mkdir()
    note = vault / "log.md"
    note.write_text(MEMORY.format(a="x" * 300, b="y" * 300, c="z" * 10), encoding="utf-8")
    session = sidecar.Session(tmp_path, Settings(memory_max_bytes=400), emit=lambda e: None)
    session.open(vault)
    assert (vault / "log-archive.md").is_file()
    assert "[[log-archive]]" in note.read_text(encoding="utf-8")


def test_text_search_works_and_meaning_search_says_not_set_up() -> None:
    notes = {"a.md": "Bought tea", "b.md": "Walked the dog"}
    assert memory.search_text(notes, "TEA") == ["a.md"]
    assert memory.status(None)["ready"] is False
    with pytest.raises(NotSetUp, match="not set up"):
        memory.search_meaning(notes, "drink", None)


class FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if "tea" in t.lower() or "drink" in t.lower() else [0.0, 1.0] for t in texts
        ]


def test_meaning_search_ranks_with_an_embedder() -> None:
    notes = {"a.md": "Bought tea", "b.md": "Walked the dog"}
    ranked = memory.search_meaning(notes, "drink", FakeEmbedder())
    assert ranked[0][0] == "a.md" and ranked[0][1] > ranked[1][1]


def test_session_memory_search_reports_status_and_refuses_meaning_without_a_model(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "log.md").write_text(MEMORY.format(a="tea", b="b", c="c"), encoding="utf-8")
    session = sidecar.Session(tmp_path / "storage", Settings(), emit=lambda e: None)
    session.open(vault)
    assert session.dispatch({"method": "memory_status"})["ready"] is False
    assert session.dispatch({"method": "memory_search", "query": "tea"})["hits"] == ["log.md"]
    with pytest.raises(NotSetUp):
        session.dispatch({"method": "memory_search", "query": "tea", "mode": "meaning"})


# --- jobs --------------------------------------------------------------------------------


def test_a_job_runs_when_due_and_then_waits_for_its_interval(tmp_path: Path) -> None:
    job = jobs.Job("link-check", "Weekly link check", "link_check", 7, enabled=True)
    assert jobs.is_due(job, NOW)
    ran, results = jobs.run_due([job], NOW, {"link_check": lambda: "2 broken link(s)"})
    assert results == ["Weekly link check: 2 broken link(s)"]
    assert not jobs.is_due(ran[0], NOW + timedelta(days=6))
    assert jobs.is_due(ran[0], NOW + timedelta(days=7))
    assert jobs.is_due(jobs.Job("x", "X", "link_check", 1, enabled=False), NOW) is False


def test_job_state_is_saved_and_a_bad_request_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "jobs.json"
    listed = jobs.load(path)
    assert [j.enabled for j in listed] == [False]
    jobs.save(path, jobs.set_job(listed, "link-check", True, 3))
    again = jobs.load(path)
    assert again[0].enabled and again[0].every_days == 3
    with pytest.raises(ValueError):
        jobs.set_job(listed, "missing", True, None)
    with pytest.raises(ValueError):
        jobs.set_job(listed, "link-check", True, 0)


def test_scheduled_link_check_counts_broken_links(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# A\n\nSee [[missing]] and [[b]].\n", encoding="utf-8")
    (vault / "b.md").write_text("# B\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "storage", Settings(), emit=lambda e: None)
    session.open(vault)
    session.dispatch({"method": "set_job", "id": "link-check", "enabled": True})
    assert session.run_jobs(NOW) == ["Weekly link check: 1 broken link(s)"]
    assert session.run_jobs(NOW) == []  # not due again yet


# --- helpers -----------------------------------------------------------------------------


def test_at_most_four_helpers_run_and_a_finished_one_frees_its_slot() -> None:
    gate = threading.Event()
    events: list[str] = []

    def run(prompt: str) -> str:
        gate.wait(5)
        return f"done {prompt}"

    pool = helpers.Helpers(run, lambda e: events.append(e["text"]))
    for i in range(4):
        pool.start(f"task {i}")
    with pytest.raises(helpers.HelperLimit):
        pool.start("task 5")
    gate.set()
    for _ in range(200):
        if all(h["status"] == "done" for h in pool.list()):
            break
        threading.Event().wait(0.01)
    assert [h["status"] for h in pool.list()] == ["done"] * 4
    assert pool.start("task 6")["status"] == "running"
    assert "helper 1 done" in events


def test_a_failed_helper_reports_its_error() -> None:
    def boom(prompt: str) -> str:
        raise RuntimeError("no model")

    pool = helpers.Helpers(boom, lambda e: None)
    pool.start("hi")
    for _ in range(200):
        if pool.list()[0]["status"] != "running":
            break
        threading.Event().wait(0.01)
    assert pool.list()[0] | {"prompt": ""} == {
        "id": 1,
        "prompt": "",
        "status": "failed",
        "result": "no model",
    }


# --- skills and share --------------------------------------------------------------------


def test_skills_are_listed_and_only_installed_ones_can_be_removed(tmp_path: Path) -> None:
    (tmp_path / "tidy").mkdir()
    (tmp_path / "tidy" / "SKILL.md").write_text(
        "---\nname: tidy\ndescription: Keeps notes neat\n---\n"
    )
    (tmp_path / "loose").mkdir()
    assert skills.list_skills(tmp_path) == [
        {
            "name": "tidy",
            "description": "Keeps notes neat",
            "path": str((tmp_path / "tidy").resolve()),
        }
    ]
    for bad in ["../tidy", "tidy/../../x", "Tidy", "", None, "loose"]:
        with pytest.raises(ValueError):
            skills.remove_skill(tmp_path, bad)
    skills.remove_skill(tmp_path, "tidy")
    assert not (tmp_path / "tidy").exists()


def test_a_skill_folder_opens_only_when_installed(tmp_path: Path) -> None:
    (tmp_path / "tidy").mkdir()
    (tmp_path / "tidy" / "SKILL.md").write_text("---\nname: tidy\n---\n")
    launched: list[list[str]] = []
    skills.open_folder(tmp_path, "tidy", launched.append)
    assert launched == [[skills.FILE_MANAGER, str((tmp_path / "tidy").resolve())]]
    for bad in ["../tidy", "Tidy", "", None]:
        with pytest.raises(ValueError):
            skills.open_folder(tmp_path, bad, launched.append)
    assert len(launched) == 1


def test_removing_a_skill_needs_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sidecar, "SKILLS_DIR", tmp_path)
    session = sidecar.Session(tmp_path / "storage", Settings(), emit=lambda e: None)
    with pytest.raises(ValueError, match="approval"):
        session.dispatch({"method": "remove_skill", "name": "x"})


def test_password_links_are_checked_and_then_refused_until_a_host_exists() -> None:
    with pytest.raises(ValueError):
        share.expiry("short")
    now = NOW
    assert share.expiry("long enough", now=now) == now + timedelta(minutes=60)
    with pytest.raises(NotSetUp, match="share host"):
        share.request_link("long enough password")


def test_share_request_reaches_the_share_check_from_the_sidecar(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    with pytest.raises(ValueError, match="at least 8"):
        session.dispatch({"method": "share", "password": "short"})
    with pytest.raises(ValueError, match="text"):
        session.dispatch({"method": "share", "password": None})
    with pytest.raises(NotSetUp, match="share host"):
        session.dispatch({"method": "share", "password": "long enough password"})


# --- keys --------------------------------------------------------------------------------


def test_keys_show_a_hint_never_the_whole_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sidecar, "get_key", lambda provider: "sk-ant-secret-a1b2" if provider == "claude" else None
    )
    monkeypatch.setattr(
        sidecar, "key_hint", lambda provider: "a1b2" if provider == "claude" else None
    )
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    rows = session.dispatch({"method": "keys"})["keys"]
    claude = rows[0]
    assert claude == {
        "provider": "claude",
        "label": "Claude (Anthropic)",
        "saved": True,
        "hint": "a1b2",
    }
    assert "sk-ant-secret" not in json.dumps(rows)
    with pytest.raises(ValueError):
        session.dispatch({"method": "save_key", "provider": "nope", "key": "x"})
