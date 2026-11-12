import threading
from pathlib import Path

import pytest

from core import __main__ as sidecar
from core import crash_log
from core.settings import Settings


def session_at(storage: Path) -> sidecar.Session:
    return sidecar.Session(storage, Settings(), emit=lambda e: None)


def test_a_recorded_error_is_read_back_newest_first(tmp_path: Path) -> None:
    session = session_at(tmp_path)
    assert session.dispatch({"method": "crashes"}) == {"crashes": []}
    session.dispatch(
        {"method": "record_crash", "source": "Graph", "message": "first", "at": "2026-11-11T10:00:00Z"}
    )
    session.dispatch({"method": "record_crash", "source": "window", "message": "second"})
    rows = session.dispatch({"method": "crashes"})["crashes"]
    assert [row["message"] for row in rows] == ["second", "first"]
    assert rows[1] == {"at": "2026-11-11T10:00:00Z", "source": "Graph", "message": "first"}
    assert (tmp_path / crash_log.FILE).is_file()  # on disk, so it survives a restart


def test_long_and_odd_values_are_cut_and_kept_as_text(tmp_path: Path) -> None:
    row = crash_log.record(tmp_path, None, "x" * 5000)
    assert row["source"] == "None"
    assert len(row["message"]) == crash_log.MESSAGE_LIMIT


def test_the_file_is_trimmed_and_a_damaged_line_is_skipped(tmp_path: Path) -> None:
    for number in range(crash_log.TRIM_AT + 1):
        crash_log.record(tmp_path, "t", str(number))
    path = tmp_path / crash_log.FILE
    assert len(path.read_text().splitlines()) == crash_log.KEEP
    with path.open("a") as out:
        out.write("not json\n")
    assert crash_log.recent(tmp_path, 1)[0]["message"] == str(crash_log.TRIM_AT)


def test_clearing_removes_the_records(tmp_path: Path) -> None:
    session = session_at(tmp_path)
    session.dispatch({"method": "record_crash", "source": "a", "message": "b"})
    assert session.dispatch({"method": "clear_crashes"}) == {"crashes": []}
    assert not (tmp_path / crash_log.FILE).exists()


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_an_unhandled_thread_error_is_recorded(tmp_path: Path) -> None:
    previous = threading.excepthook
    restore = sidecar.record_thread_errors(tmp_path)
    try:
        worker = threading.Thread(target=lambda: 1 / 0, name="worker-x")
        worker.start()
        worker.join()
    finally:
        restore()
    assert threading.excepthook is previous
    row = crash_log.recent(tmp_path, 1)[0]
    assert row["source"] == "sidecar thread worker-x"
    assert "ZeroDivisionError" in row["message"]
