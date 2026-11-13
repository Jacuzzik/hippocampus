"""Scheduled jobs, helpers, watchers and the memory trim: the parts of the session that run work in the background."""

import asyncio
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ai.keys import get_api_key
from ai.router import build_router
from core import jobs as job_store
from core import (
    link_doctor,
    webhooks,
)
from core import memory as memory_notes
from core.helpers import HelperLimit
from core.vault.scanner import iter_notes


def _watcher(
    name: str, kind: str, status: str, last_event: str | None = None
) -> dict[str, str | None]:
    return {"name": name, "kind": kind, "status": status, "last_event": last_event}


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

    @property
    def jobs_path(self) -> Path:
        return self.storage / "jobs.json"

    def run_jobs(self, now: datetime | None = None) -> list[str]:
        """Run each enabled job that is due. Called on a timer by `serve`."""
        if self.indexer is None:
            return []
        runners = {"link_check": self._link_check}
        jobs, results = job_store.run_due(
            job_store.load(self.jobs_path), now or datetime.now().astimezone(), runners
        )
        job_store.save(self.jobs_path, jobs)
        for line in results:
            self.note("handoff", text=line)
        return results

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

    def link_doctor(self) -> dict[str, Any]:
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            return link_doctor.report(self.indexer.store)

    def helpers_state(self) -> dict[str, Any]:
        return {"helpers": self.helpers.list(), "limit": 4}

    def watchers_state(self) -> dict[str, Any]:
        """Background watchers, read only. `watch` runs VaultWatcher, not `serve`, so the
        vault row is always stopped here; the minute timer runs triggers only with a vault."""
        rows: list[dict[str, str | None]] = []
        if self.indexer is not None:
            rows.append(_watcher(self.indexer.vault.name, "vault watcher", "stopped"))
        for job in job_store.load(self.jobs_path):
            on = "running" if job.enabled and self.indexer is not None else "stopped"
            rows.append(_watcher(job.name, "trigger", on, job.last_run))
        for hook in webhooks.load(self.webhooks_path):  # saved only: nothing listens for them
            rows.append(_watcher(hook["name"], "webhook", "stopped"))
        status = {"running": "running", "done": "stopped", "failed": "error"}
        for job in self.helpers.list():
            name = f"helper {job['id']}: {job['prompt'][:40]}"
            rows.append(_watcher(name, "helper", status[job["status"]]))
        # Every agent with a terminal: running or stopped, and when it last started or stopped.
        for agent in sorted(set(self.terminals.events) | set(self.terminals.procs)):
            running = (
                agent in self.terminals.procs and self.terminals.procs[agent][0].poll() is None
            )
            last = self.terminals.events.get(agent)
            last_event = f"{datetime.fromtimestamp(last[0]):%H:%M} {last[1]}" if last else None
            # "hippoherman" is the main agent's terminal id; show it by its name.
            shown = "Hippoherman (main agent)" if agent == "hippoherman" else agent
            rows.append(_watcher(shown, "agent", "running" if running else "stopped", last_event))
        return {"watchers": rows}

    def system_state(self) -> dict[str, Any]:
        """CPU, RAM and disk use in percent. Disk is the drive that holds the app data."""
        return self.system.read(self.storage)

    def start_helper(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt")
        if not isinstance(prompt, str):
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
