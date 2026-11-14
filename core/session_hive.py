"""Messages between agents: the hub notes, the daily compact, and typing waiting messages into each agent's terminal."""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core import (
    added_agents,
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


class HivePart:
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
                except RuntimeError:
                    pass
                del self.compact_waiting[agent]

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
                if inbox.collect_outboxes(self.hive_path, self._agent_ids()):
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
                    if not folder.is_dir():
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
        return True
