"""Notes pinned to an agent reach its briefing at start, and their cost is reported with a warning (N.23)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from core import __main__ as sidecar
from core import briefing, pins
from core.settings import Settings
from tests.core.test_briefing import FakeTerminals


def test_paths_drop_blanks_repeats_and_non_text() -> None:
    assert pins.paths({"pinned": ["a.md", "", "a.md", 3, "b.md"]}) == ["a.md", "b.md"]
    assert pins.paths({"pinned": "a.md"}) == []
    assert pins.paths({}) == []


def test_gather_cuts_long_notes_and_names_missing_ones() -> None:
    notes = {"long.md": "x" * (pins.CHARS_MAX + 10), "short.md": "hello"}

    def read(path: str) -> str:
        if path not in notes:
            raise ValueError("no note at that path")
        return notes[path]

    long_row, short_row, gone = pins.gather(["long.md", "short.md", "gone.md"], read)
    assert long_row["cut"] and len(long_row["text"]) == pins.CHARS_MAX
    assert long_row["tokens"] == pins.CHARS_MAX // 4
    assert short_row["tokens"] == 2 and not short_row["cut"]
    assert gone["missing"].startswith("Could not read it")
    body = pins.section([long_row, short_row, gone])
    assert "--- short.md ---\nhello" in body and "gone.md" not in body
    assert "(cut here" in body
    assert pins.gather(["a.md"], None)[0]["missing"] == "No vault is open."


def test_summary_warns_past_the_limit_and_leaves_the_text_out() -> None:
    rows = [
        {"path": "a.md", "text": "t", "tokens": pins.TOKENS_WARN + 1, "cut": False, "missing": ""}
    ]
    out = pins.summary(rows)
    assert out["warn"] and out["tokens"] == pins.TOKENS_WARN + 1
    assert "text" not in out["notes"][0]
    assert not pins.summary([])["warn"]


def test_add_section_numbers_after_the_last_section() -> None:
    text = briefing.add_section("1. Role\nx\n\n2. Goal\ny", "Pinned notes", "body")
    assert text.endswith("3. Pinned notes\nbody")


def _session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pinned: list[str]) -> sidecar.Session:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Rules.md").write_text("Always write tests first.", encoding="utf-8")
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session.terminals = FakeTerminals()  # type: ignore[assignment]
    session.indexer = SimpleNamespace(vault=vault.resolve())  # type: ignore[assignment]
    monkeypatch.setattr(
        sidecar.added_agents, "load", lambda path: [{"id": "ada", "name": "Ada", "pinned": pinned}]
    )
    return session


def test_a_pinned_note_is_in_the_briefing_and_the_sections_stay_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _session(tmp_path, monkeypatch, ["Rules.md", "Missing.md"])
    session.dispatch(
        {"method": "terminal_start", "agent": "ada", "provider": "claude", "rows": 24, "cols": 80}
    )
    (text,) = session.terminals.briefings
    assert "Pinned notes\nThe user pinned" in text and "Always write tests first." in text
    assert briefing.lint(text) == []
    cost = session.dispatch({"method": "agent_pins", "agent": "ada"})
    assert [n["path"] for n in cost["notes"]] == ["Rules.md", "Missing.md"]
    assert cost["notes"][1]["missing"] and cost["tokens"] > 0 and not cost["warn"]


def test_no_pins_adds_no_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session(tmp_path, monkeypatch, [])
    session.dispatch(
        {"method": "terminal_start", "agent": "ada", "provider": "claude", "rows": 24, "cols": 80}
    )
    assert "Pinned notes" not in session.terminals.briefings[0]


def test_a_handoff_note_is_loaded_into_the_next_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _session(tmp_path, monkeypatch, [])
    vault = session.indexer.vault  # type: ignore[union-attr]
    (vault / "ada-Handoff.md").write_text("State: half done\nNext: tests", encoding="utf-8")
    session.dispatch(
        {"method": "terminal_start", "agent": "ada", "provider": "claude", "rows": 24, "cols": 80}
    )
    (text,) = session.terminals.briefings
    assert "Handoff from your last session\nYour last session left this in ada-Handoff.md" in text
    assert "Next: tests" in text and "rewrite ada-Handoff.md" in text
    assert briefing.lint(text) == []


def test_no_handoff_note_adds_no_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session(tmp_path, monkeypatch, [])
    session.dispatch(
        {"method": "terminal_start", "agent": "ada", "provider": "claude", "rows": 24, "cols": 80}
    )
    assert "Handoff from your last session" not in session.terminals.briefings[0]
