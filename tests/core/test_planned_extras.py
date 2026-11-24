"""Features that were Planned: update check (G.04), calendars by iCal address, Notion, search by
meaning (7.09) and plugins (D.07)."""

import io
import json
import time
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


class FakeSlack:
    """Slack's Web API as the bot sees it: a few conversations, new messages, and the replies it posted."""

    def __init__(self) -> None:
        self.history: list[dict[str, Any]] = []
        self.posted: list[dict[str, str]] = []

    def __call__(self, token: str, method: str, params: dict[str, str]) -> dict[str, Any]:
        assert token.startswith("xoxb-")
        if method == "auth.test":
            return {"ok": True, "team": "Acme", "user": "hippo", "user_id": "UBOT"}
        if method == "users.conversations":
            return {
                "channels": [
                    {"id": "C1234567", "name": "ops", "is_channel": True},
                    {"id": "D1234567", "is_im": True, "user": "UANN"},
                ]
            }
        if method == "conversations.history":
            assert params["channel"] == "C1234567"
            return {
                "messages": [m for m in self.history if float(m["ts"]) > float(params["oldest"])]
            }
        assert method == "chat.postMessage"
        self.posted.append(params)
        return {"ok": True}


def test_the_slack_bridge_forwards_chosen_messages_and_posts_the_agent_answer_in_the_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import core.__main__ as sidecar
    import core.session_extras as extras
    from core import inbox
    from core.settings import Settings

    store: dict[str, str] = {}
    monkeypatch.setattr(extras.keys, "get_key", store.get)
    monkeypatch.setattr(extras.keys, "set_key", lambda name, value: store.__setitem__(name, value))
    monkeypatch.setattr(extras.keys, "clear_key", lambda name: store.pop(name, None))
    monkeypatch.setattr(extras.network, "mode", lambda: "open")
    session = sidecar.Session(tmp_path, Settings())
    fake = FakeSlack()
    session._slack_call = fake  # type: ignore[attr-defined]

    with pytest.raises(ValueError, match="xoxb-"):
        session.dispatch({"method": "slack_connect", "token": "nope"})
    token = "xoxb-" + "1" * 30
    state = session.dispatch({"method": "slack_connect", "token": token})
    assert state["connected"] and state["workspace"] == "Acme" and not state["on"]
    assert "slack-bot" in store and token not in json.dumps(state)
    rows = session.dispatch({"method": "slack_conversations"})["rows"]
    assert [r["kind"] for r in rows] == ["channel", "dm"]

    with pytest.raises(ValueError, match="agent that exists"):
        session.dispatch(
            {"method": "slack_set", "channels": ["C1234567"], "agent": "ghost", "on": True}
        )
    session.dispatch(
        {"method": "slack_set", "channels": ["C1234567"], "agent": "hippoherman", "on": True}
    )
    fake.history = [
        {"ts": "1.0", "user": "UANN", "text": "old, before the bridge"},
        {"ts": f"{time.time() + 5:.6f}", "user": "UANN", "text": "please summarise the week"},
        {"ts": f"{time.time() + 6:.6f}", "user": "UBOT", "text": "my own message"},
        {"ts": f"{time.time() + 7:.6f}", "user": "UANN", "bot_id": "B1", "text": "another bot"},
    ]
    session.slack_tick()
    [(path, message)] = inbox.pending(session.hive_path, "hippoherman")
    assert "please summarise the week" in message["body"] and message["from"] == "user"
    assert message["work"].startswith("slack:C1234567:")
    session.slack_tick()  # nothing is forwarded twice
    assert len(inbox.pending(session.hive_path, "hippoherman")) == 1

    # The agent answers the user with the same work id; the answer is posted in the thread.
    inbox.send(
        session.hive_path, "hippoherman", "user", "Re", "Here is the summary.", work=message["work"]
    )
    session.slack_last = 0.0
    session.slack_tick()
    assert fake.posted[0]["text"] == "Here is the summary."
    assert fake.posted[0]["thread_ts"] == message["work"].split(":")[2]
    assert not inbox.pending(session.hive_path, "user")

    # An answer for a conversation that was not chosen is refused, never posted.
    inbox.send(
        session.hive_path, "hippoherman", "user", "Re", "x", work="slack:C9999999:1700000000.1"
    )
    session.slack_last = 0.0
    session.slack_tick()
    assert len(fake.posted) == 1 and not inbox.pending(session.hive_path, "user")
    state = session.dispatch({"method": "slack_state"})
    assert (state["forwarded"], state["answered"]) == (1, 1)
    assert not session.dispatch({"method": "slack_disconnect"})["connected"]


class FakeTeamService:
    """The team tables and functions, in memory, as one signed-in person sees them."""

    def __init__(self, shared: dict[str, Any]) -> None:
        self.db = shared
        self.me = "u1"

    def status(self) -> dict[str, Any]:
        return {"signed_in": True, "configured": True}

    def _data(self, path: str, body: Any = None, method: str = "POST", prefer: str = "") -> Any:
        db = self.db
        if path.endswith("/rpc/create_team"):
            team = {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": body["p_name"],
                "code": "abcdef012345",
            }
            db["teams"] = [team]
            db["members"] = [{"email": "a@x.org", "role": "owner", "user": self.me}]
            return [team]
        if path.endswith("/rpc/join_team"):
            if body["p_code"] != "abcdef012345":
                raise ValueError("The account service said no: no team has that code")
            db["members"].append({"email": "b@x.org", "role": "member", "user": "u2"})
            return [db["teams"][0]]
        if "team_members?select=role,teams" in path:
            owner = self.me == "u1"
            return [
                {"role": "owner" if owner else "member",
                 "teams": {"id": db["teams"][0]["id"], "name": db["teams"][0]["name"], "join_code": db["teams"][0]["code"]}}
            ]  # fmt: skip
        if "team_members?team_id" in path:
            return [{"email": m["email"], "role": m["role"]} for m in db["members"]]
        if path.startswith("/rest/v1/team_items?on_conflict"):
            for row in body:
                db.setdefault("items", {})[(row["kind"], row["name"])] = row["body"]
            return None
        if path.startswith("/rest/v1/team_items?team_id"):
            return [
                {"kind": k, "name": n, "body": b, "updated_at": "2026-11-24"}
                for (k, n), b in db.get("items", {}).items()
            ]
        raise AssertionError(path)


def test_a_team_shares_agents_task_titles_and_notes_between_two_people(
    tmp_path: Path,
) -> None:
    import core.__main__ as sidecar
    from core import added_agents
    from core.settings import Settings

    shared: dict[str, Any] = {}
    vault_a, vault_b = tmp_path / "va", tmp_path / "vb"
    for vault in (vault_a, vault_b):
        (vault).mkdir()
    (vault_a / "Team").mkdir()
    (vault_a / "Team" / "Plan.md").write_text("# Plan\nship it\n", encoding="utf-8")
    (vault_a / "Private.md").write_text("mine", encoding="utf-8")

    ann = sidecar.Session(tmp_path / "a", Settings(vault=vault_a))
    ann.user_account = FakeTeamService(shared)  # type: ignore[assignment]
    added_agents.save(
        ann.agents_path,
        [
            {
                "id": "ada",
                "name": "Ada",
                "provider": "claude",
                "model": "m",
                "folder": "/home/ann/secret",
                "command": "x",
            }
        ],
    )
    state = ann.dispatch({"method": "team_create", "name": "Core team"})
    team = state["teams"][0]
    assert team["code"] == "abcdef012345" and team["role"] == "owner"
    done = ann.dispatch({"method": "team_save", "team": team["id"]})
    assert done["agents"] == 1 and done["notes"] == 1
    assert "Private.md" not in str(shared["items"].keys())
    assert (
        "secret" not in shared["items"][("agents", "")]
        and "command" not in shared["items"][("agents", "")]
    )

    bob = sidecar.Session(tmp_path / "b", Settings(vault=vault_b))
    bob.user_account = FakeTeamService(shared)  # type: ignore[assignment]
    bob.user_account.me = "u2"  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="12 letters"):
        bob.dispatch({"method": "team_join", "code": "nope"})
    bob.dispatch({"method": "team_join", "code": "abcdef012345"})
    seen = bob.dispatch({"method": "teams_state", "team": team["id"]})
    assert seen["teams"][0]["code"] == "" and [m["email"] for m in seen["members"]] == [
        "a@x.org",
        "b@x.org",
    ]
    assert seen["shared"]["agents"] == ["Ada"] and seen["shared"]["notes"] == ["Team/Plan.md"]
    got = bob.dispatch({"method": "team_get", "team": team["id"]})
    assert got == {"agents_added": ["Ada"], "notes_written": 1, "notes_unchanged": 0}
    assert (vault_b / "Team" / "Plan.md").read_text(encoding="utf-8") == "# Plan\nship it\n"
    assert added_agents.load(bob.agents_path)[0]["folder"] == ""
    again = bob.dispatch({"method": "team_get", "team": team["id"]})
    assert again == {"agents_added": [], "notes_written": 0, "notes_unchanged": 1}


def test_teams_need_a_sign_in_and_explain_a_service_that_is_not_set_up(tmp_path: Path) -> None:
    import core.__main__ as sidecar
    from core import teams
    from core.settings import Settings

    session = sidecar.Session(tmp_path, Settings())

    class SignedOut:
        def status(self) -> dict[str, Any]:
            return {"signed_in": False, "configured": True}

    session.user_account = SignedOut()  # type: ignore[assignment]
    assert session.dispatch({"method": "teams_state"})["signed_in"] is False
    with pytest.raises(ValueError, match="Sign in first"):
        session.dispatch({"method": "team_create", "name": "x"})

    def missing(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("The account service said no: 404 Could not find the table")

    with pytest.raises(ValueError, match="20261124_teams.sql"):
        teams.Teams(missing).mine()
    with pytest.raises(ValueError, match="not a note in the Team folder"):
        teams.write_note(tmp_path, "../x.md", "x")
    with pytest.raises(ValueError, match="not a team id"):
        teams.Teams(missing).leave("../../x")
