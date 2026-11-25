"""Scheduled jobs, helpers, watchers and the memory trim: the parts of the session that run work in the background."""

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ai.keys import get_api_key
from ai.router import build_router
from core import activity as journal
from core import (
    calendar_board,
    contract,
    daily_brief,
    inbox,
    link_doctor,
)
from core import jobs as job_store
from core import memory as memory_notes
from core import missions as mission_store
from core.helpers import HelperLimit
from core.vault.scanner import iter_notes
from tools.vault_tools import vault_tools


class JobsPart:
    def trim_memory(self) -> list[str]:
        """Move the oldest sections of long memory notes to archive notes. Runs on each open."""
        if self.indexer is None:
            return []
        changed: list[Path] = []
        for note in iter_notes(self.indexer.vault):
            path = self.indexer.vault / note.path
            archive = memory_notes.trim_memory_file(
                self.indexer.vault, path, self.settings.memory_max_bytes
            )
            if archive is not None:
                changed += [path, archive]
                self.note("setting", text=f"trimmed {note.path} into {archive.name}")
        if changed:
            with self.lock:
                self.indexer.apply_changes(changed)
        return [p.name for p in changed]

    def jobs(self) -> dict[str, Any]:
        return {"jobs": [asdict(j) for j in job_store.load(self.jobs_path)]}

    def set_job(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = request.get("id")
        if not isinstance(job_id, str) or not isinstance(request.get("enabled"), bool):
            raise ValueError('"set_job" needs an "id" and "enabled"')
        every = request.get("every_days")
        jobs = job_store.set_job(job_store.load(self.jobs_path), job_id, request["enabled"], every)
        job_store.save(self.jobs_path, jobs)
        return self.jobs()

    def run_job(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run one scheduled job now. The user's click is the approval; nothing runs without it."""
        job_id = request.get("id")
        if not isinstance(job_id, str):
            raise ValueError('"run_job" needs an "id"')
        if request.get("approve") is not True:
            raise ValueError("running a job needs the user's approval")
        if self.indexer is None:
            raise ValueError("no vault is open")
        jobs, result = job_store.run_now(
            job_store.load(self.jobs_path),
            job_id,
            datetime.now().astimezone(),
            {"link_check": self._link_check, "daily_brief": self._daily_brief},
        )
        job_store.save(self.jobs_path, jobs)
        self.note("approval", tool="run_job", tier="act", approved=True, by="card")
        self.note("handoff", text=result)
        return {**self.jobs(), "result": result}

    @property
    def events_path(self) -> Path:
        return self.storage / "events.json"

    def calendar(self, request: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().astimezone()
        self._calendar_settle()
        month = request.get("month") or now.date().isoformat()[:7]
        view = calendar_board.month_view(
            self.events_path, job_store.load(self.jobs_path), month, now.date()
        )
        view["upcoming"] = calendar_board.upcoming(self.events_path, now)
        view["agents"] = sorted(self._agent_ids())
        return view

    def calendar_add(self, request: dict[str, Any]) -> dict[str, Any]:
        event = calendar_board.add(
            self.events_path,
            request.get("date"),
            request.get("time"),
            request.get("title"),
            request.get("note"),
            request.get("agent"),
            self._agent_ids(),
        )
        return self.calendar({"month": event["date"][:7]})

    def calendar_mark(self, request: dict[str, Any]) -> dict[str, Any]:
        calendar_board.set_status(self.events_path, request.get("id"), request.get("status"))
        return self.calendar({"month": request.get("month")})

    def _calendar_settle(self) -> list[str]:
        lines = calendar_board.settle(self.events_path, inbox.all_messages(self.hive_path))
        for line in lines:
            self.note("handoff", text=line)
        return lines

    def run_calendar(self, now: datetime | None = None) -> list[str]:
        """Send each calendar event whose time has come to its agent, and read the agents' answers."""
        now = now or datetime.now().astimezone()

        def send(event: dict[str, str]) -> None:
            when = f"{event['date']} {event['time'] or calendar_board.DEFAULT_TIME}"
            objective = (
                f'The user put this on their calendar for {when}: "{event["title"]}".'
                + (f"\n\nDetails: {event['note']}" if event["note"] else "")
                + "\n\nIt is that time now. If it is a reminder, remind the user. If it asks for work"
                " you can do, do it now."
            )
            output = (
                'When you have finished, write one message to "user" with "work": "'
                + event["id"]
                + '". Use "act": "done" and say what you did when it is completed, or "act": "refuse"'
                " and say why when it could not be done. The calendar shows a check or a cross from it."
            )
            inbox.send(
                self.hive_path,
                inbox.USER,
                event["agent"],
                f"Calendar: {event['title']}",
                contract.build({"objective": objective, "output": output}),
                act="request",
                work=event["id"],
            )

        lines = self._calendar_settle() + calendar_board.send_due(self.events_path, now, send)
        for line in lines:
            self.note("handoff", text=line)
        if lines:
            self.changed("inbox")
        return lines

    def calendar_remove(self, request: dict[str, Any]) -> dict[str, Any]:
        calendar_board.remove(self.events_path, request.get("id"))
        return self.calendar({"month": request.get("month")})

    @property
    def jobs_path(self) -> Path:
        return self.storage / "jobs.json"

    @property
    def missions_path(self) -> Path:
        return self.storage / "missions.json"

    def missions(self) -> dict[str, Any]:
        rows = [asdict(m) for m in mission_store.load(self.missions_path)]
        return {"missions": rows, "cap": mission_store.CAP}

    def mission_save(self, request: dict[str, Any]) -> dict[str, Any]:
        """Add a mission, or change one (with its "id"). Switching one on or off is a change too."""
        row = request.get("mission")
        if not isinstance(row, dict):
            raise ValueError('"mission_save" needs a "mission" object')
        agent = str(row.get("agent") or "")
        if agent and agent not in self._agent_ids():
            raise ValueError(f'No agent has the id "{agent}".')
        missions = mission_store.upsert(mission_store.load(self.missions_path), row)
        mission_store.save(self.missions_path, missions)
        return self.missions()

    def mission_remove(self, request: dict[str, Any]) -> dict[str, Any]:
        missions = mission_store.remove(mission_store.load(self.missions_path), request.get("id"))
        mission_store.save(self.missions_path, missions)
        return self.missions()

    def run_missions(self, now: datetime | None = None) -> list[str]:
        """Send each switched-on mission that is due, as a message from the user. Needs no vault."""
        missions = mission_store.load(self.missions_path)
        if not any(m.enabled for m in missions):
            return []

        def send(mission: mission_store.Mission) -> None:
            inbox.send(
                self.hive_path,
                inbox.USER,
                mission.agent,
                mission.label,
                contract.wrap(mission.message),
                act="request",
                work=mission.id,
            )

        missions, lines = mission_store.run_due(missions, now or datetime.now().astimezone(), send)
        mission_store.save(self.missions_path, missions)
        for line in lines:
            self.note("handoff", text=line)
        if lines:
            self.changed("inbox")
        return lines

    def run_jobs(self, now: datetime | None = None) -> list[str]:
        """Run each enabled job and mission that is due. Called on a timer by `serve`."""
        sent = self.run_calendar(now) + self.run_missions(now)
        if self.indexer is None:
            return sent
        runners = {"link_check": self._link_check, "daily_brief": self._daily_brief}
        jobs, results = job_store.run_due(
            job_store.load(self.jobs_path), now or datetime.now().astimezone(), runners
        )
        job_store.save(self.jobs_path, jobs)
        for line in results:
            self.note("handoff", text=line)
        return sent + results

    def _link_check(self) -> str:
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            store = self.indexer.store
            broken = sum(
                1
                for path in store.note_states()
                for _raw, target in store.outgoing(path)
                if target is None
            )
        return f"{broken} broken link(s)"

    def _daily_brief(self) -> str:
        """Write today's brief note from what the app already holds; no model is called."""
        if self.indexer is None:
            raise ValueError("no vault is open")
        now = datetime.now().astimezone()
        day = now.date()
        yesterday = (day - timedelta(days=1)).isoformat()
        text = daily_brief.compose(
            day,
            calendar_board.upcoming(self.events_path, now.replace(hour=0, minute=0), 12)
            + self.feed_events(),
            self.tasks()["tasks"],
            self.fleet_state()["agents"],
            len(inbox.pending(self.hive_path, inbox.USER)),
            journal.read(self.storage, since=yesterday, until=yesterday),
        )
        path = daily_brief.path_for(day)
        tools = vault_tools(self.indexer, self.lock)
        try:
            tools["edit_note"].run({"path": path, "content": text})
        except FileNotFoundError:
            tools["create_note"].run({"path": path, "content": text})
        self.changed("notes")
        return f"wrote the daily brief {path}"

    def link_doctor(self) -> dict[str, Any]:
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            return link_doctor.report(self.indexer.store)

    def helpers_state(self) -> dict[str, Any]:
        return {"helpers": self.helpers.list(), "limit": 4}

    def system_state(self) -> dict[str, Any]:
        """CPU, RAM and disk use in percent. Disk is the drive that holds the app data."""
        return self.system.read(self.storage)

    def start_helper(self, request: dict[str, Any]) -> dict[str, Any]:
        # 8.05: every task goes out as a four-part contract. "parts" holds them; a plain "prompt" is the objective.
        parts = request.get("parts")
        if isinstance(parts, dict):
            prompt = contract.build(parts)
        elif isinstance(request.get("prompt"), str):
            prompt = contract.wrap(request["prompt"])
        else:
            raise ValueError('"prompt" must be text')
        over = self.ledger.first_overrun({"app": (self.settings.budget, None)})
        if over is not None and not self.allowance:
            raise ValueError(f"the app {over.window} token cap is used; allow a request first")
        try:
            self.helpers.start(prompt)
        except HelperLimit as exc:
            raise ValueError(str(exc)) from exc
        return self.helpers_state()

    def _helper_run(self, prompt: str) -> str:
        router = build_router(self.settings, get_api_key())
        reply = asyncio.run(router.chat([{"role": "user", "content": prompt}], []))
        self.ledger.add("helper", reply.tokens)
        return reply.text
