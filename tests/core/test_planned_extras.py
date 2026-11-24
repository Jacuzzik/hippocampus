"""Features that were Planned: update check (G.04), calendars by iCal address, Notion, search by
meaning (7.09) and plugins (D.07)."""

import io
import json
import zipfile
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from core import ical_feed, notion, semantic, terminal, updates
from core.plugins import Plugins


def test_update_check_says_when_a_newer_version_is_out() -> None:
    body = json.dumps(
        {"tag_name": "v9.0.0", "body": "New things", "html_url": "https://x"}
    ).encode()
    found = updates.check(lambda url, headers: (200, body))
    assert found["newer"] and found["latest"] == "v9.0.0" and found["notes"] == "New things"
    assert not updates.check(lambda url, headers: (404, b""))["newer"]
    assert not updates.newer("0.0.9", "0.1.0") and updates.newer("0.1.1", "0.1.0")
    with pytest.raises(ValueError, match="GitHub answered 500"):
        updates.check(lambda url, headers: (500, b""))


ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;TZID=Asia/Dubai:20261124T090000
SUMMARY:Stand-up\\, team
RRULE:FREQ=WEEKLY;BYDAY=TU,TH
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261126
SUMMARY:Holiday
END:VEVENT
BEGIN:VEVENT
DTSTART:20261125T120000Z
SUMMARY:Cancelled call
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
DTSTART:20261101T120000Z
SUMMARY:Long ago
END:VEVENT
END:VCALENDAR
"""


def test_a_calendar_link_gives_the_next_two_weeks() -> None:
    dubai = ZoneInfo("Asia/Dubai")
    events = ical_feed.parse(ICS, date(2026, 11, 24), dubai)
    titles = [(e["date"], e["time"], e["title"]) for e in events]
    assert titles[:3] == [
        ("2026-11-24", "09:00", "Stand-up, team"),
        ("2026-11-26", "", "Holiday"),
        ("2026-11-26", "09:00", "Stand-up, team"),
    ]
    assert all(e["title"] not in ("Cancelled call", "Long ago") for e in events)
    assert len([e for e in events if e["title"] == "Stand-up, team"]) == 5
    assert ical_feed.check_link("webcal://cal.example.com/x.ics").startswith("https://")
    with pytest.raises(ValueError, match="secret iCal address"):
        ical_feed.check_link("not a link")


def test_a_notion_page_becomes_markdown() -> None:
    page = "a" * 32

    def call(token: str, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == f"/pages/{page}":
            return {"object": "page", "url": "https://notion.so/p",
                    "properties": {"Name": {"type": "title", "title": [{"plain_text": "Plan"}]}}}  # fmt: skip
        return {"results": [
            {"id": "b1", "type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Goals"}]}},
            {"id": "b2", "type": "to_do", "to_do": {"checked": True, "rich_text": [{"plain_text": "Ship"}]}},
        ], "has_more": False}  # fmt: skip

    title, text = notion.page_markdown("ntn_" + "x" * 30, page, call)
    assert title == "Plan" and "# Goals" in text and "- [x] Ship" in text
    assert notion.note_path("A/B: c") == "Notion/A B c.md"
    with pytest.raises(ValueError, match="ntn_"):
        notion.check_token("nope")


def test_search_by_meaning_finds_the_closest_note(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "cats.md").write_text("Cats purr and sleep.", encoding="utf-8")
    (vault / "money.md").write_text("Budget and invoices.", encoding="utf-8")
    (vault / ".hidden").mkdir()
    (vault / ".hidden" / "x.md").write_text("cats", encoding="utf-8")

    def embed(texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if "cat" in t.lower() or "kitten" in t.lower() else [0.0, 1.0] for t in texts
        ]

    store = tmp_path / "embeddings.json"
    assert semantic.build(vault, store, embed) == {"notes": 2, "read": 2}
    assert semantic.build(vault, store, embed)["read"] == 0  # unchanged notes are not read again
    assert semantic.search("kitten", store, embed)[0]["path"] == "cats.md"


def _zip(files: dict[str, str]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as pack:
        for name, text in files.items():
            pack.writestr(name, text)
    return out.getvalue()


def test_a_plugin_installs_switches_and_reaches_the_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugins = Plugins(tmp_path)
    data = _zip({
        "pack/.claude-plugin/plugin.json": json.dumps({"name": "writer", "version": "1.0"}),
        "pack/skills/draft/SKILL.md": "---\nname: draft\n---\n",
        "pack/.mcp.json": json.dumps({"mcpServers": {"docs": {"command": "x"}}}),
    })  # fmt: skip
    [row] = plugins.install("writer.zip", data)
    assert (row["name"], row["skills"], row["servers"], row["enabled"]) == (
        "writer",
        1,
        ["docs"],
        True,
    )
    assert plugins.enabled_dirs() == [str(tmp_path / "plugins" / "writer")]
    plugins.set_enabled("writer", False)
    assert plugins.enabled_dirs() == []
    with pytest.raises(ValueError, match="leaves its folder"):
        plugins.install(
            "bad.zip", _zip({".claude-plugin/plugin.json": '{"name": "bad"}', "../evil": "x"})
        )
    with pytest.raises(ValueError, match="not a plugin"):
        plugins.install("none.zip", _zip({"readme.md": "x"}))
    assert plugins.remove("writer") == []

    monkeypatch.setattr(terminal.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(terminal.cli_sessions, "FILE", tmp_path / "sessions.json")
    argv = terminal._command("ada", "claude", plugin_dirs=["/p/one"])
    assert argv[argv.index("--plugin-dir") + 1] == "/p/one"
    assert "--plugin-dir" not in terminal._command(
        "ada", "claude", block_tools=True, plugin_dirs=["/p"]
    )


def test_trail_notes_are_asked_for_and_a_missing_one_shows(tmp_path: Path) -> None:
    from datetime import date as day

    from core import briefing

    text = briefing.trail_section("Ada#1")
    assert "Trails/Ada-1/YYYY-MM-DD.md" in text and "Decided" in text
    folder = tmp_path / "Trails" / "Ada-1"
    folder.mkdir(parents=True)
    (folder / f"{day.today().isoformat()}.md").write_text("x", encoding="utf-8")
    ada, bo = briefing.trails(tmp_path, ["Ada#1", "Bo"])
    assert ada["recent"] and ada["path"] == f"Trails/Ada-1/{day.today().isoformat()}.md"
    assert not bo["recent"] and bo["newest"] == ""
    joined = briefing.add_section(briefing.AGENT.split("\n\n2.")[0], "Trail note", text)
    assert joined.count("2. Trail note") == 1


def test_the_demo_vault_is_labelled_linked_and_never_overwrites_edits(tmp_path: Path) -> None:
    from core import demo_vault
    from core.vault.parser import parse_note

    folder = demo_vault.build(tmp_path)
    assert demo_vault.is_demo(tmp_path, folder) and not demo_vault.is_demo(tmp_path, tmp_path)
    assert len(list(folder.glob("*.md"))) == len(demo_vault.NOTES) >= 12
    start = (folder / "Start here.md").read_text(encoding="utf-8")
    assert "Demo vault" in start
    stems = {name[:-3] for name in demo_vault.NOTES}
    links = 0
    for name, text in demo_vault.NOTES.items():
        for link in parse_note(text, name).links:
            assert link.target_raw in stems, f"{name} links to a missing note"
            links += 1
    assert links >= 30
    (folder / "Start here.md").write_text("mine", encoding="utf-8")
    demo_vault.build(tmp_path)
    assert (folder / "Start here.md").read_text(encoding="utf-8") == "mine"


def test_usage_statistics_count_the_local_log_only(tmp_path: Path) -> None:
    from core import activity, usage_stats

    assert usage_stats.summarize(tmp_path)["total"] == 0
    activity.record(tmp_path, "tool", tool="read_note", tier="read", status="done", agent="kelly")
    activity.record(tmp_path, "tool", tool="write_note", tier="write", status="failed")
    activity.record(tmp_path, "approval", tool="write_note", tier="write", approved=True)
    activity.record(tmp_path, "approval", tool="delete_note", tier="act", approved=False)
    found = usage_stats.summarize(tmp_path)
    assert found["total"] == 4 and found["failed_tools"] == 1
    assert found["approvals"] == {"asked": 2, "approved": 1, "declined": 1}
    assert found["agents"] == [{"name": "kelly", "count": 1}]
    assert len(found["days"]) == 14 and found["days"][-1]["count"] == 4
    assert "Nothing is collected" in found["statement"]


def _git(folder: Path, *args: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


def test_the_code_editor_reads_saves_and_shows_git_inside_the_folder(tmp_path: Path) -> None:
    from core import code_editor as ce

    folder = tmp_path / "agent"
    folder.mkdir()
    (tmp_path / "secret.txt").write_text("no", encoding="utf-8")
    (folder / "a.py").write_text("print(1)\n", encoding="utf-8")
    (folder / "bin.dat").write_bytes(b"\0\1\2")
    (folder / "sub").mkdir()
    (folder / "node_modules").mkdir()
    assert [r["name"] for r in ce.tree(folder, "")] == ["sub", "a.py", "bin.dat"]
    assert ce.read(folder, "a.py")["text"] == "print(1)\n"
    for bad in ("../secret.txt", "/etc/passwd", "bin.dat"):
        with pytest.raises(ValueError):
            ce.read(str(folder), bad)
    with pytest.raises(ValueError, match="outside"):
        ce.save(str(folder), "../x.txt", "x")
    ce.save(str(folder), "sub/new.txt", "hello")
    assert (folder / "sub" / "new.txt").read_text(encoding="utf-8") == "hello"

    assert ce.changes(str(folder))["repo"] is False
    _git(folder, "init", "-b", "main")
    _git(folder, "add", ".")
    _git(folder, "commit", "-m", "first")
    ce.save(str(folder), "a.py", "print(2)\n")
    found = ce.changes(str(folder))
    assert found["branch"] == "main" and found["files"] == [{"state": "M", "path": "a.py"}]
    assert "+print(2)" in ce.diff(str(folder), "a.py")
    assert ce.history(str(folder))[0]["subject"] == "first"
    _git(folder, "checkout", "-b", "feature")
    ce.save(str(folder), "b.txt", "b")
    _git(folder, "add", "b.txt")
    _git(folder, "commit", "-m", "second")
    versus = ce.compare(str(folder), "main", "feature")
    assert versus["ahead"] == 1 and versus["files"] == [{"state": "A", "path": "b.txt"}]
    with pytest.raises(ValueError, match="exist"):
        ce.compare(str(folder), "main", "--output=x")


def test_an_agent_that_asks_first_waits_for_the_app_and_shows_the_exact_change(
    tmp_path: Path,
) -> None:
    import threading
    import time

    from core import approval_hook, approvals

    base = tmp_path / "approvals"
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    edit = {
        "tool_name": "Edit",
        "cwd": str(work),
        "tool_input": {"file_path": str(work / "a.txt"), "old_string": "two", "new_string": "2"},
    }

    def answer_when_waiting(decision: str) -> None:
        for _ in range(100):
            rows = approvals.waiting(base)
            if rows:
                assert rows[0]["agent"] == "ada" and "-two" in rows[0]["diff"]
                assert "+2" in rows[0]["diff"]
                approvals.answer(base, rows[0]["id"], decision)
                return
            time.sleep(0.05)

    thread = threading.Thread(target=answer_when_waiting, args=("deny",))
    thread.start()
    assert approval_hook.decide(base, "ada", edit)[0] == "deny"
    thread.join()
    assert not approvals.waiting(base)

    # "Approve for this folder" is remembered: the next edit there is allowed with no request.
    thread = threading.Thread(target=answer_when_waiting, args=("folder",))
    thread.start()
    assert approval_hook.decide(base, "ada", edit)[0] == "allow"
    thread.join()
    assert approval_hook.decide(base, "ada", edit) == ("allow", "approved earlier for this folder")
    assert approvals.rules(base)[0] == {"tool": "Edit", "folder": str(work)}
    approvals.remove_rule(base, 0)
    assert not approvals.rules(base)


def test_a_shell_rule_covers_one_command_word_and_never_a_chain(tmp_path: Path) -> None:
    from core import approvals

    rule = approvals.rule_for({"tool": "Bash", "cwd": str(tmp_path), "command": "npm test"})
    assert rule["prefix"] == "npm"
    assert approvals.matches(rule, "Bash", str(tmp_path), "npm run build")
    assert not approvals.matches(rule, "Bash", str(tmp_path), "rm -rf x")
    assert not approvals.matches(rule, "Bash", str(tmp_path), "npm test && rm -rf x")
    assert not approvals.matches(rule, "Bash", str(tmp_path.parent), "npm test")
    assert not approvals.matches(rule, "Edit", str(tmp_path), "npm test")


def test_no_answer_never_approves_and_the_kill_switch_denies_everything(tmp_path: Path) -> None:
    from core import approvals

    base = tmp_path / "approvals"
    rid = approvals.request(base, "ada", "Bash", str(tmp_path), {"command": "ls"})
    assert approvals.wait_for(base, rid, seconds=0.2, step=0.05) is None
    assert approvals.deny_all(base) == 1
    assert approvals.wait_for(base, rid, seconds=1, step=0.05) == "deny"
    with pytest.raises(ValueError, match="no longer waiting"):
        approvals.answer(base, "missing", "once")
    with pytest.raises(ValueError, match="decision"):
        approvals.answer(base, rid, "maybe")


def test_only_agents_that_ask_first_get_the_approval_hook(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from core import terminal

    monkeypatch.setattr(terminal.shutil, "which", lambda name: f"/bin/{name}")
    ask = terminal._command("ada", "claude", level="ask", approvals_dir=tmp_path)
    assert "--settings" in ask and "core.approval_hook" in ask[ask.index("--settings") + 1]
    assert "PreToolUse" in ask[ask.index("--settings") + 1]
    for argv in (
        terminal._command("ada", "claude", level="edits", approvals_dir=tmp_path),
        terminal._command("hippoherman", "claude", level="ask", approvals_dir=tmp_path),
        terminal._command("ada", "claude", level="ask", block_tools=True, approvals_dir=tmp_path),
        terminal._command("ada", "claude", level="ask"),
    ):
        assert "core.approval_hook" not in " ".join(argv)
