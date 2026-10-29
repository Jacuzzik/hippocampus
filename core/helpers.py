"""Short-lived helper jobs: each runs one prompt once and reports back. At most four run at once."""

import itertools
import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("hippocampus.helpers")
MAX_RUNNING = 4
KEEP = 20  # finished helpers kept for the list


class HelperLimit(Exception):
    pass


class Helpers:
    def __init__(
        self, run: Callable[[str], str], on_event: Callable[[dict[str, Any]], None]
    ) -> None:
        self._run = run
        self._on_event = on_event
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._jobs: dict[int, dict[str, Any]] = {}

    def start(self, prompt: str) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError('"prompt" is empty')
        with self._lock:
            running = sum(1 for job in self._jobs.values() if job["status"] == "running")
            if running >= MAX_RUNNING:
                raise HelperLimit(
                    f"{MAX_RUNNING} helpers are already running; wait for one to finish"
                )
            job = {
                "id": next(self._ids),
                "prompt": prompt.strip(),
                "status": "running",
                "result": "",
            }
            self._jobs[job["id"]] = job
            self._trim()
            snapshot = dict(job)
        self._on_event({"text": f"helper {job['id']} started"})
        threading.Thread(target=self._work, args=(job,), daemon=True).start()
        return snapshot

    def _work(self, job: dict[str, Any]) -> None:
        try:
            result, status = self._run(job["prompt"]), "done"
        except Exception as exc:
            logger.exception("Helper %s failed", job["id"])
            result, status = str(exc), "failed"
        with self._lock:
            job["result"], job["status"] = result, status
        self._on_event({"text": f"helper {job['id']} {status}"})

    def _trim(self) -> None:
        finished = [i for i, job in self._jobs.items() if job["status"] != "running"]
        for job_id in finished[: max(0, len(self._jobs) - KEEP)]:
            del self._jobs[job_id]

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(job) for job in self._jobs.values()]
