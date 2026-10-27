"""Scheduled notes jobs. Each job repeats every N days. Its state lives in storage/jobs.json.

The sidecar checks the list about once a minute and runs each enabled job that is due.
"""

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("hippocampus.jobs")
KINDS = ("link_check",)
DEFAULTS = (
    {"id": "link-check", "name": "Weekly link check", "kind": "link_check", "every_days": 7},
)
_lock = threading.Lock()


@dataclass(frozen=True)
class Job:
    id: str
    name: str
    kind: str
    every_days: int
    enabled: bool = False
    last_run: str | None = None


def load(path: Path) -> list[Job]:
    """The saved jobs, with any default job missing from the file added (switched off)."""
    saved: dict[str, dict[str, object]] = {}
    if path.is_file():
        try:
            for row in json.loads(path.read_text(encoding="utf-8")):
                saved[str(row["id"])] = row
        except (ValueError, KeyError, TypeError):
            logger.warning("jobs file is unreadable; using the defaults")
    jobs = []
    for default in DEFAULTS:
        row = {**default, "enabled": False, "last_run": None, **saved.get(default["id"], {})}
        jobs.append(Job(**{k: row[k] for k in Job.__dataclass_fields__}))
    return jobs


def save(path: Path, jobs: list[Job]) -> None:
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([asdict(job) for job in jobs], indent=2), encoding="utf-8")


def set_job(jobs: list[Job], job_id: str, enabled: bool, every_days: int | None) -> list[Job]:
    if not any(job.id == job_id for job in jobs):
        raise ValueError(f"no job named {job_id}")
    if every_days is not None and (not isinstance(every_days, int) or every_days < 1):
        raise ValueError('"every_days" must be a whole number of 1 or more')
    out = []
    for job in jobs:
        if job.id == job_id:
            job = replace(job, enabled=enabled, every_days=every_days or job.every_days)
        out.append(job)
    return out


def is_due(job: Job, now: datetime) -> bool:
    if not job.enabled:
        return False
    if job.last_run is None:
        return True
    return now - datetime.fromisoformat(job.last_run) >= timedelta(days=job.every_days)


def run_due(
    jobs: list[Job], now: datetime, runners: dict[str, Callable[[], str]]
) -> tuple[list[Job], list[str]]:
    """Run each due job once. Returns the updated jobs and one result line per job run."""
    out, results = [], []
    for job in jobs:
        if is_due(job, now):
            try:
                results.append(f"{job.name}: {runners[job.kind]()}")
            except Exception:
                logger.exception("Job %s failed", job.id)
                results.append(f"{job.name}: failed")
            job = replace(job, last_run=now.isoformat(timespec="seconds"))
        out.append(job)
    return out, results
