"""A scheduled job can be run at once, whether or not it is due or switched on."""

from datetime import datetime

import pytest

from core import jobs


def test_run_now_runs_a_job_that_is_off_and_stamps_it() -> None:
    now = datetime(2026, 11, 15, 9, 0).astimezone()
    saved = [jobs.Job("link-check", "Weekly link check", "link_check", 7)]
    out, result = jobs.run_now(
        saved, "link-check", now, {"link_check": lambda: "3 links, all fine"}
    )
    assert result == "Weekly link check: 3 links, all fine"
    assert out[0].last_run == now.isoformat(timespec="seconds")
    assert out[0].enabled is False  # running it once does not switch it on


def test_run_now_reports_a_failure_and_refuses_an_unknown_job() -> None:
    now = datetime(2026, 11, 15, 9, 0).astimezone()
    saved = [jobs.Job("link-check", "Weekly link check", "link_check", 7)]

    def broken() -> str:
        raise RuntimeError("boom")

    _, result = jobs.run_now(saved, "link-check", now, {"link_check": broken})
    assert result == "Weekly link check: failed"
    with pytest.raises(ValueError, match="no job named"):
        jobs.run_now(saved, "nope", now, {})
