"""Messages between agents: the hub notes, the daily compact, and typing waiting messages into each agent's terminal."""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ai import cli_sessions
from core import (
    added_agents,
    breaker,
    commit_queue,
    crash_log,
    file_requests,
    fleet,
    inbox,
    startup_inbox,
)
from core.session_shared import (
    COMPACT_PROMPT,
    COMPACT_SAVE_PROMPT,
    DELIVERY_BODY_MAX,
    DELIVERY_MAX_WAIT_S,
    INBOX_SETTLE_S,
)

FLEET_SECONDS = 15


class HivePart:
    def fleet_rows(self) -> list[dict[str, Any]]:
        """One row per agent for the fleet file: status, model, context use and inbox backlog."""
        added = [
            (str(a["id"]), str(a.get("name") or a["id"]))
            for a in added_agents.load(self.agents_path)
            if a.get("id")
        ]
        terminals = self.terminals
        return fleet.build(
            [("hippoherman", "Hippoherman"), *added],
            terminals.info,
            cli_sessions.context_percent,
            lambda agent: len(inbox.pending(self.hive_path, agent)),
            terminals.started_at,
            terminals.last_output,
        )

    def fleet_state(self) -> dict[str, Any]:
        rows = self.fleet_rows()
        for row in rows:
            row["breaker"] = self.breakers.get(row["id"], {}).get("level", "healthy")
        return {
            "path": str(self.hive_path / fleet.NAME),
            "requests": str(self.hive_path / file_requests.FOLDER),
            "commits": str(self.hive_path / commit_queue.FOLDER),
            "agents": rows,
        }

    def _check_breakers(self, rows: list[dict[str, Any]]) -> None:
        """Assess each running agent and steer a tripped one, once per reason per cooldown."""
        crashes = crash_log.recent(self.storage, 200)
        now = time.time()
        seen: dict[str, dict[str, Any]] = {}
        for row in rows:
            agent = row["id"]
            if row["status"] not in ("working", "idle"):
                found = breaker.assess(agent, [], None, crashes)
            else:
                found = breaker.assess(
                    agent, cli_sessions.tool_trace(agent, 20), row["context_percent"], crashes
                )
            seen[agent] = found
            for reason in found["reasons"]:
                key = (agent, reason["kind"])
                line = breaker.steer_text(reason, COMPACT_PROMPT.format(agent=agent))
                if line is None or now - self.breaker_sent.get(key, 0.0) < breaker.COOLDOWN_S:
                    continue
                if row["status"] not in ("working", "idle"):
                    continue
                self.breaker_sent[key] = now
                try:
                    self.terminals.send_line(agent, line)
                except RuntimeError:
                    continue
                self.note("budget", text=f"circuit breaker steered {agent}: {reason['text']}")
                self.alert(f"Circuit breaker: {row.get('name', agent)}", reason["text"])
        if {a: f["level"] for a, f in seen.items()} != {
            a: f["level"] for a, f in self.breakers.items()
        }:
            self.changed("fleet")
        self.breakers = seen

    def breakers_state(self) -> dict[str, Any]:
        return {"breakers": list(self.breakers.values())}

    def _alert_new(self) -> None:
        """A desktop alert for a new message for the user or a new question waiting. The first
        check only counts, so starting the app does not alert for what was already there."""
        unread = len(inbox.pending(self.hive_path, inbox.USER))
        asks = len(self.asks.waiting()) + len(self.gate.waiting())
        if 0 <= self.seen_unread < unread:
            self.alert("A message for you", f"{unread} unread in the Inbox.")
        if 0 <= self.seen_asks < asks:
            self.alert("A question is waiting", "Open Ask me to answer it.")
        self.seen_unread, self.seen_asks = unread, asks

    def _take_requests(self) -> None:
        """Turn request files dropped in the hive's requests folder into inbox messages (7.35)."""

        def send(request: dict[str, str]) -> None:
            inbox.send(
                self.hive_path,
                inbox.USER,
                request["to"],
                request["subject"],
                request["body"],
                act="request",
                work=request["work"],
                priority=request["priority"],
            )

        sent, failed = file_requests.process(self.hive_path, self._agent_ids(), send)
        if sent:
            self.note("handoff", text=f"took {sent} request file(s) from the requests folder")
            self.changed("inbox")
        if failed:
            self.note(
                "error", text=f"{failed} request file(s) could not be read; see requests/.failed"
            )

    def _take_commits(self) -> None:
        """Commit what agents asked for, one request at a time (7.11)."""
        allowed = [
            Path(str(a["folder"])) for a in added_agents.load(self.agents_path) if a.get("folder")
        ]
        if self.settings.vault:
            allowed.append(Path(self.settings.vault))
        lines = commit_queue.process(self.hive_path, allowed, self._agent_ids())
        for line in lines:
            self.note("handoff" if line.startswith("committed") else "error", text=line)

    def _write_fleet(self) -> None:
        now = time.time()
        if now - self.last_fleet < FLEET_SECONDS:
            return
        self.last_fleet = now
        rows = self.fleet_rows()
        try:
            self._check_breakers(rows)
        except OSError:
            logging.exception("Could not check the circuit breakers")
        for row in rows:
            row["breaker"] = self.breakers.get(row["id"], {}).get("level", "healthy")
        try:
            fleet.write(self.hive_path, rows, now)
        except OSError:
            logging.exception("Could not write the fleet file")

    def _hubs_present(self) -> None:
        # Re-creates any missing hub note straight away, so a deleted hub comes back without a restart.
        vault = self.settings.vault
        if not vault or not Path(vault).is_dir():
            return
        groups = ["Projects", "Summaries", "Agent Lists", "Contacts", "Socials", "About User"]
        links = "".join(f"- [[{name}]]\n" for name in groups)
        main = f"# MAIN\n\nInstructions for all agents. Read this first.\n\n- Work in your own folder and the vault. Do not change other agents' notes.\n- Before you compact, save your notes and a summary to your own note.\n- When the user gives a rule or instruction to keep for good, write it into your own -PriorityNotes note in the vault, creating the note if it does not exist.\n- If you do not know something, search the vault before you ask.\n- Only the user deletes a note linked to a group.\n\nGroups:\n\n{links}"
        bodies = {
            "Projects": "Active projects: the goal, the status, and links to the notes for it. One note per project, linked here.",
            "Summaries": "Daily summaries that each agent saves before it compacts: what it did, what it decided, what is still open. One note per day, linked here.",
            "Agent Lists": "Every agent in the app: what it does, its status (active, archived or deleted) and where its memory is kept. One note per agent, linked here. Only the user can edit, delete or remove these notes.",
            "Contacts": "People the user works with. Each contact has a name, a phone number (if they have one), an optional label, and a line on who they are. A phone number always needs a name: if you do not have one, ask the user for it. One note per person, linked here.",
            "Socials": "The user's accounts on every platform: platform, account name or handle, profile link, and purpose. Never store passwords, logins or keys here.",
            "About User": "Facts about the user that agents need: role, preferences and how they like replies. Change it only when the user says so.",
        }
        notes = {"MAIN": main}
        notes.update({name: f"# {name}\n\n{bodies[name]}\n" for name in groups})
        for name, body in notes.items():
            path = Path(vault) / f"{name}.md"
            if not path.exists():
                path.write_text(body, encoding="utf-8")

    def _daily_compact(self) -> None:
        # Once a day, from 03:00: every running agent is asked to save its notes, then compacts once it is idle again.
        now = datetime.now()
        if (
            self.compact_day != now.date().isoformat()
            and now.hour >= 3
            and not self.compact_waiting
        ):
            self.compact_day = now.date().isoformat()
            for agent in list(self.terminals.procs):
                if self.terminals.info(agent)["status"] is None:
                    continue
                try:
                    self.terminals.send_line(agent, COMPACT_SAVE_PROMPT.format(agent=agent))
                    self.compact_waiting[agent] = time.time()
                except RuntimeError:
                    continue
        for agent, sent_at in list(self.compact_waiting.items()):
            # Wait at least 20 seconds so the save has started, and only compact when the agent is Idle.
            if time.time() - sent_at >= 20 and self.terminals.info(agent)["status"] == "Idle":
                try:
                    self.terminals.send_line(agent, COMPACT_PROMPT.format(agent=agent))
                    self.resend_after_compact[agent] = time.time()
                except RuntimeError:
                    pass
                del self.compact_waiting[agent]
        # 8.12: once the compaction is done and the agent is Idle again, point it at its briefing again.
        for agent, sent_at in list(self.resend_after_compact.items()):
            if time.time() - sent_at < 20 or self.terminals.info(agent)["status"] != "Idle":
                continue
            del self.resend_after_compact[agent]
            try:
                self.terminals.resend_briefing(agent)
            except RuntimeError:
                pass

    def _write_all_inboxes(self) -> None:
        """Writes the start-up inbox file for every added agent and for the main agent."""
        agents = added_agents.load(self.agents_path)
        for agent in ["hippoherman", *[a["id"] for a in agents if a.get("id")]]:
            try:
                startup_inbox.write(self.hive_path, agent, agents)
            except OSError:
                logging.exception("Could not write the start-up inbox for %s", agent)

    def _deliver_loop(self) -> None:
        # Every few seconds: move agent replies into inboxes, then type each waiting message into its running terminal.
        while True:
            time.sleep(self.settings.delivery_seconds)
            try:
                self._hubs_present()
                self._daily_compact()
                self._write_fleet()
                self._alert_new()
                self._take_requests()
                self._take_commits()
                # "user" is a valid receiver: an agent answers the user there (a calendar event's done or refuse).
                if inbox.collect_outboxes(self.hive_path, self._agent_ids() | {inbox.USER}):
                    self.changed("inbox")
                # Once a day, old delivered messages move into one compressed file per month.
                if time.time() - self.last_archive > 86400:
                    self.last_archive = time.time()
                    inbox.archive_old(self.hive_path)
                if not self.hive_path.is_dir():
                    continue
                for agent, inbox_file in list(self.inbox_pending.items()):
                    if time.time() - self.terminals.started_at.get(agent, 0.0) < INBOX_SETTLE_S:
                        continue
                    path = Path(inbox_file)
                    text = startup_inbox.for_chat(
                        path.read_text(encoding="utf-8") if path.is_file() else "", path
                    )
                    try:
                        self.terminals.send_line(agent, text)
                    except RuntimeError:
                        pass
                    self.inbox_pending.pop(agent, None)
                for folder in self.hive_path.iterdir():
                    # The user and the app have no terminal: their messages are read in the Inbox.
                    if not folder.is_dir() or folder.name in (
                        inbox.USER,
                        inbox.APP,
                        file_requests.FOLDER,
                    ):
                        continue
                    # A terminal that has just started is still drawing: messages typed before it is ready are lost, so they wait for it to settle.
                    if (
                        time.time() - self.terminals.started_at.get(folder.name, 0.0)
                        < INBOX_SETTLE_S
                    ):
                        continue
                    for path, message in inbox.pending(self.hive_path, folder.name):
                        if not self._deliver(folder.name, path, message):
                            break
                        self.changed("inbox")
            except Exception:
                logging.exception("Could not deliver agent messages")

    def _deliver(self, agent: str, path: Path, message: dict[str, Any]) -> bool:
        """Type one queued message into the agent's terminal and file it. False means stop for now:
        the terminal is busy or closed, or the two agents are being held apart."""
        sender = str(message.get("from") or "")
        if not self.loop_guard.allow(sender, agent):
            pair = (min(sender, agent), max(sender, agent))
            # One alert per hold, not one per poll.
            if time.time() - self.loop_alerts.get(pair, 0.0) > self.loop_guard.cooldown:
                self.loop_alerts[pair] = time.time()
                minutes = round(self.loop_guard.cooldown / 60)
                text = f"{sender} and {agent} sent each other more than {self.loop_guard.limit} messages in a minute. Their messages are held for {minutes} minutes."
                self.note("error", text=text)
                self.emit({"event": "message_loop", "agents": list(pair), "text": text})
            return False
        urgent = " (urgent)" if message.get("priority") == "urgent" else ""
        work = f" Task {message.get('work')}." if message.get("work") else ""
        body = str(message.get("body") or "")
        if len(body) > DELIVERY_BODY_MAX:
            body = body[:DELIVERY_BODY_MAX] + " ...(cut: the full text is in the app's Inbox tab)"
        # Wording follows the start-up inbox: the app files the message, and an acknowledgement-only reply is not wanted.
        text = (
            f"New {message.get('act') or 'request'}{urgent} from {sender}. Subject: {message.get('subject')}.{work} "
            f"{body} "
            f'To answer, put "replyTo": "{message.get("id")}" in your message. '
            "The app files it for you, so do not open or move the inbox files. Act on it; reply only if your work needs it."
        )
        text = " ".join(text.split())
        try:
            waited = time.time() - float(message.get("at") or time.time())
            # A busy CLI can drop or mangle typed text, so wait for it to go quiet. A CLI that never
            # goes quiet (some redraw all the time) still gets the message after a while.
            if waited < DELIVERY_MAX_WAIT_S:
                if not self.terminals.send_line_when_quiet(agent, text):
                    return False
            else:
                self.terminals.send_line(agent, text)
        except RuntimeError:
            return False  # the terminal is not running: the message stays queued
        inbox.mark_done(path)
        # The agent bar flies an envelope from the sender's card to the receiver's (N.03, 12.10).
        self.emit({"event": "message_sent", "from": sender, "to": agent})
        return True
