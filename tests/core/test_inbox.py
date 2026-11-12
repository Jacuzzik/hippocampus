import gzip
import json
import os
import time
from pathlib import Path

import pytest

from core import __main__ as sidecar
from core import inbox
from core.settings import Settings

KNOWN = {"hippoherman", "ada", "bob"}


def drop(hive: Path, agent: str, name: str, content: object) -> Path:
    outbox = hive / agent / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / name
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def states(hive: Path) -> dict[str, str]:
    return {str(row["subject"]): row["state"] for row in inbox.all_messages(hive)}


def test_a_message_has_the_full_schema_and_a_reply_joins_its_thread(tmp_path: Path) -> None:
    first = inbox.send(
        tmp_path,
        "hippoherman",
        "ada",
        "Tidy notes",
        "Sort the inbox folder",
        work="T-1",
        priority="urgent",
    )
    reply = inbox.send(
        tmp_path, "ada", "hippoherman", "DONE: T-1", "Sorted 4 notes", act="done", reply_to=first
    )
    rows = {row["id"]: row for row in inbox.all_messages(tmp_path)}
    assert (
        rows[first]["act"] == "request"
        and rows[first]["work"] == "T-1"
        and rows[first]["priority"] == "urgent"
    )
    assert (
        rows[first]["thread"] == first
        and rows[reply]["thread"] == first
        and rows[reply]["replyTo"] == first
    )
    assert [row["id"] for row in inbox.thread(tmp_path, first)] == [first, reply]
    assert "## ada to hippoherman (done, queued)" in inbox.export_thread(tmp_path, first)


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"to": ""}, 'no "to"'),
        ({"act": "shout"}, '"act" must be one of'),
        ({"priority": "now"}, '"priority" must be'),
        ({"subject": "", "body": ""}, "empty"),
    ],
)
def test_a_wrong_field_is_refused_with_a_plain_reason(fields: dict[str, str], reason: str) -> None:
    base = {"to": "ada", "subject": "s", "body": "b", "act": "request", "priority": "normal"}
    base.update(fields)
    with pytest.raises(ValueError, match=reason):
        inbox.new_message(
            "hippoherman",
            base["to"],
            base["subject"],
            base["body"],
            act=base["act"],
            priority=base["priority"],
        )


def test_urgent_messages_are_read_first(tmp_path: Path) -> None:
    inbox.send(tmp_path, "hippoherman", "ada", "first", "x")
    inbox.send(tmp_path, "hippoherman", "ada", "second", "x", priority="urgent")
    assert [m["subject"] for _, m in inbox.pending(tmp_path, "ada")] == ["second", "first"]


def test_the_sender_is_the_folder_not_what_the_file_claims(tmp_path: Path) -> None:
    drop(
        tmp_path,
        "ada",
        "m.json",
        {"from": "hippoherman", "to": "bob", "subject": "Do this", "body": "now 1"},
    )
    assert inbox.collect_outboxes(tmp_path, KNOWN) == 1
    [(_, message)] = inbox.pending(tmp_path, "bob")
    assert message["from"] == "ada"  # ada cannot send as the main agent


def test_bad_files_fail_with_a_reason_and_the_sender_is_told(tmp_path: Path) -> None:
    drop(tmp_path, "ada", "broken.json", "{not json")
    drop(tmp_path, "ada", "nobody.json", {"to": "zed", "subject": "Hi there 1", "body": "x"})
    drop(tmp_path, "ada", "self.json", {"to": "ada", "subject": "Note 1", "body": "x"})
    assert inbox.collect_outboxes(tmp_path, KNOWN) == 0
    failed = sorted((tmp_path / "ada" / "outbox" / ".failed").glob("*.json"))
    reasons = [json.loads(f.read_text())["failed"] for f in failed]
    assert reasons == [
        "The file is not valid JSON.",
        'No agent has the id "zed". Use an id from your start-up inbox.',
        "A message to yourself is not delivered.",
    ]
    told = [m for _, m in inbox.pending(tmp_path, "ada")]
    assert len(told) == 3 and all(m["from"] == "app" and m["act"] == "inform" for m in told)
    assert not (tmp_path / "zed").exists()  # no folder is made for an agent that does not exist


@pytest.mark.parametrize("text", ["ok", "Thanks!", "Got it, thanks.", "noted", "Will do"])
def test_an_acknowledgement_only_message_is_dropped(tmp_path: Path, text: str) -> None:
    drop(tmp_path, "ada", "ack.json", {"to": "bob", "subject": "", "body": text})
    assert inbox.collect_outboxes(tmp_path, KNOWN) == 0
    assert inbox.pending(tmp_path, "bob") == []
    assert len(list((tmp_path / "ada" / "outbox" / ".dropped").glob("*.json"))) == 1
    [(_, told)] = inbox.pending(tmp_path, "ada")
    assert "only acknowledged" in told["body"]


@pytest.mark.parametrize(
    "message",
    [
        {"subject": "DONE: T-4", "body": "ok"},  # carries a task id
        {"subject": "", "body": "ok, which folder?"},  # asks something
        {"subject": "", "body": "done", "act": "done"},  # the act is the answer
        {
            "subject": "",
            "body": "Thanks. The build is green and the notes are linked from Projects now.",
        },
    ],
)
def test_a_short_message_that_carries_something_is_kept(message: dict[str, str]) -> None:
    assert inbox.is_ack_only(message) is False


def test_a_note_is_filed_without_being_queued(tmp_path: Path) -> None:
    drop(
        tmp_path,
        "ada",
        "n.json",
        {"to": "bob", "act": "note", "subject": "FYI vault moved", "body": "New path is /v2"},
    )
    assert inbox.collect_outboxes(tmp_path, KNOWN) == 1
    assert inbox.pending(tmp_path, "bob") == []  # nothing to type: a note wakes nobody
    assert states(tmp_path)["FYI vault moved"] == "delivered"


def test_delivery_moves_a_message_from_queued_to_delivered_once(tmp_path: Path) -> None:
    inbox.send(tmp_path, "hippoherman", "ada", "Task 1", "x")
    [(path, _)] = inbox.pending(tmp_path, "ada")
    assert states(tmp_path)["Task 1"] == "queued"
    inbox.mark_done(path)
    assert inbox.pending(tmp_path, "ada") == []
    assert states(tmp_path)["Task 1"] == "delivered"
    # A crash between typing and filing leaves the file queued, never lost: there is no third place it can be.
    assert not path.exists() and (path.parent / ".done" / path.name).exists()


def test_search_matches_every_word(tmp_path: Path) -> None:
    inbox.send(tmp_path, "hippoherman", "ada", "Tidy the vault", "Fix broken links", work="T-9")
    inbox.send(tmp_path, "hippoherman", "bob", "Write summary", "Of the call")
    assert [r["subject"] for r in inbox.search(tmp_path, "vault links")] == ["Tidy the vault"]
    assert [r["subject"] for r in inbox.search(tmp_path, "T-9")] == ["Tidy the vault"]
    assert inbox.search(tmp_path, "   ") == []


def test_the_loop_guard_holds_a_chatty_pair_then_lets_go(tmp_path: Path) -> None:
    guard = inbox.LoopGuard(limit=3, window=60, cooldown=300)
    assert [guard.allow("ada", "bob", now=100 + n) for n in range(3)] == [True, True, True]
    assert guard.allow("bob", "ada", now=104) is False  # the fourth in a minute, either direction
    assert guard.held("ada", "bob", now=200) and guard.allow("ada", "bob", now=200) is False
    assert guard.allow("ada", "hippoherman", now=200) is True  # another pair is not affected
    assert guard.allow("ada", "bob", now=405) is True  # the hold ends
    assert all(guard.allow("user", "ada", now=500) for _ in range(50))  # the human is never held


def test_old_delivered_messages_move_into_a_monthly_archive(tmp_path: Path) -> None:
    inbox.send(tmp_path, "hippoherman", "ada", "Old one", "x")
    inbox.send(tmp_path, "hippoherman", "ada", "New one", "x")
    for path, message in inbox.pending(tmp_path, "ada"):
        inbox.mark_done(path)
        if message["subject"] == "Old one":
            done = path.parent / ".done" / path.name
            old = time.time() - 40 * 86400
            os.utime(done, (old, old))
    assert inbox.archive_old(tmp_path, days=30) == 1
    assert list(states(tmp_path)) == ["New one"]
    [archive] = (tmp_path / "ada" / "archive").glob("*.jsonl.gz")
    with gzip.open(archive, "rt", encoding="utf-8") as handle:
        assert json.loads(handle.readline())["subject"] == "Old one"


class FakeTerminals:
    def __init__(self) -> None:
        self.typed: list[tuple[str, str]] = []
        self.quiet = True
        self.started_at: dict[str, float] = {}

    def send_line_when_quiet(self, agent: str, text: str) -> bool:
        if self.quiet:
            self.typed.append((agent, text))
        return self.quiet

    def send_line(self, agent: str, text: str) -> None:
        self.typed.append((agent, text))


def session_at(tmp_path: Path) -> sidecar.Session:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session.terminals = FakeTerminals()  # type: ignore[assignment]
    return session


def test_a_busy_terminal_keeps_the_message_queued_until_it_is_quiet(tmp_path: Path) -> None:
    session = session_at(tmp_path)
    hive = session.hive_path
    inbox.send(hive, "hippoherman", "ada", "Task 7", "Do it", work="T-7", priority="urgent")
    [(path, message)] = inbox.pending(hive, "ada")
    session.terminals.quiet = False
    assert session._deliver("ada", path, message) is False
    assert states(hive)["Task 7"] == "queued"
    session.terminals.quiet = True
    assert session._deliver("ada", path, message) is True
    assert states(hive)["Task 7"] == "delivered"
    [(agent, text)] = session.terminals.typed
    assert agent == "ada" and text.startswith(
        "New request (urgent) from hippoherman. Subject: Task 7. Task T-7. Do it"
    )
    assert f'"replyTo": "{message["id"]}"' in text


def test_a_message_that_waited_too_long_is_sent_even_to_a_busy_terminal(tmp_path: Path) -> None:
    session = session_at(tmp_path)
    inbox.send(session.hive_path, "hippoherman", "ada", "Task 8", "Do it")
    [(path, message)] = inbox.pending(session.hive_path, "ada")
    message["at"] = time.time() - sidecar.DELIVERY_MAX_WAIT_S - 1
    session.terminals.quiet = False
    assert session._deliver("ada", path, message) is True


def test_the_human_can_message_one_agent_or_all(tmp_path: Path, monkeypatch) -> None:
    session = session_at(tmp_path)
    monkeypatch.setattr(session, "_agent_ids", lambda: {"hippoherman", "ada", "bob"})
    sent = session.dispatch(
        {
            "method": "task_send",
            "to": "all",
            "from": "user",
            "subject": "Stand-up",
            "body": "Report in",
            "priority": "urgent",
        }
    )
    assert len(sent["ids"]) == 3
    rows = session.dispatch({"method": "inbox"})["messages"]
    assert {row["to"] for row in rows} == {"hippoherman", "ada", "bob"} and {
        row["from"] for row in rows
    } == {"user"}
    with pytest.raises(ValueError, match="No agent has the id"):
        session.dispatch({"method": "task_send", "to": "zed", "subject": "x", "body": "y"})
    found = session.dispatch({"method": "inbox_search", "query": "stand-up"})["messages"]
    assert len(found) == 3
    thread = session.dispatch({"method": "inbox_thread", "thread": rows[0]["thread"]})
    assert thread["markdown"].startswith("# Stand-up")
