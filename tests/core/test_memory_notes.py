"""The memory list also says the size cap, so the window can draw a meter."""

from pathlib import Path

import pytest

from core.__main__ import Session
from core.settings import Settings


def test_memory_list_carries_the_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hive = tmp_path / "hive"
    (hive / "agents" / "kevin").mkdir(parents=True)
    (hive / "agents" / "kevin" / "memory.md").write_text("x" * 100)
    monkeypatch.setenv("MD_HIVE_DIR", str(hive))
    session = Session(
        storage=tmp_path / "storage",
        settings=Settings(memory_max_bytes=5000),
        settings_path=tmp_path / "settings.toml",
    )
    found = session.memory_notes()
    assert found["max_bytes"] == 5000
    assert found["notes"][0]["agent"] == "kevin"
    assert found["notes"][0]["bytes"] == 100


def test_note_counts_tell_rules_from_notes_and_find_repeats() -> None:
    from core.session_memory import note_counts

    text = "\n".join(
        [
            "# Memory",
            "## Rules (never moved)",
            "- Always run the tests",
            "- Never print a key",
            "## Notes",
            "- The vault lives in Documents",
            "- the  vault lives in documents",
            "plain text is not counted",
            "- ",
        ]
    )
    assert note_counts(text) == {"rules": 2, "notes": 2, "repeated": 1}


def test_memory_list_carries_the_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hive = tmp_path / "hive"
    (hive / "agents" / "pam").mkdir(parents=True)
    (hive / "agents" / "pam" / "memory.md").write_text("## Rules\n- one\n## Notes\n- two\n- two\n")
    monkeypatch.setenv("MD_HIVE_DIR", str(hive))
    session = Session(
        storage=tmp_path / "storage",
        settings=Settings(),
        settings_path=tmp_path / "settings.toml",
    )
    row = session.memory_notes()["notes"][0]
    assert (row["rules"], row["notes"], row["repeated"]) == (1, 2, 1)


def test_condense_drops_repeated_list_lines_and_blank_runs_but_not_frontmatter() -> None:
    from core import memory

    text = "---\ncreated_by: assistant\ntags:\n- a\n- a\n---\n# M\n\n\n\n- Run tests\n-  run   TESTS\n- Other\n"
    out = memory.condense(text)
    assert out.startswith("---\ncreated_by: assistant\ntags:\n- a\n- a\n---\n")
    assert out.count("un tests") + out.count("un   TESTS") == 1
    assert "\n\n\n" not in out and "- Other" in out


def test_trim_keeps_the_rules_section_and_moves_the_oldest_notes() -> None:
    from core import memory

    text = (
        "# M\n## Rules (never moved)\n- keep me\n"
        + "## 2026-01 notes\n"
        + "a" * 200
        + "\n"
        + "## 2026-02 notes\n"
        + "b" * 200
        + "\n"
        + "## 2026-03 notes\n- newest\n"
    )
    kept, moved = memory.trim_text(text, 300, "M")
    assert "## Rules (never moved)\n- keep me" in kept and "newest" in kept
    assert "Rules" not in moved and "2026-01" in moved


def test_a_memory_file_over_the_cap_is_condensed_before_anything_moves(tmp_path: Path) -> None:
    from core import memory

    path = tmp_path / "log.md"
    body = "---\ncreated_by: assistant\n---\n# Log\n## Notes\n" + "- same line\n" * 40
    path.write_text(body, encoding="utf-8")
    assert memory.trim_memory_file(tmp_path, path, 200) is None  # condensing was enough
    assert path.read_text(encoding="utf-8").count("- same line") == 1
