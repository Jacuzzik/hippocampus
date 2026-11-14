"""Privacy: the activity history can be emptied, and new events are still written after it."""

from pathlib import Path

import core.__main__ as sidecar
from core import activity
from core.settings import Settings


def test_clearing_empties_the_history_and_new_events_still_land(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    activity.record(tmp_path, "setting", text="one")
    activity.record(tmp_path, "tool", text="two")
    assert len(session.dispatch({"method": "activity"})["rows"]) == 2
    assert session.dispatch({"method": "clear_activity"}) == {"rows": []}
    assert session.dispatch({"method": "activity"})["rows"] == []
    activity.record(tmp_path, "setting", text="three")
    assert [row["text"] for row in session.dispatch({"method": "activity"})["rows"]] == ["three"]


def test_clearing_with_no_history_file_is_not_an_error(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    assert session.dispatch({"method": "clear_activity"}) == {"rows": []}
