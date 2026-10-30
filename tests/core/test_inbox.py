import json
from pathlib import Path

from core.__main__ import Session


def _write(folder: Path, name: str, created: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps({"id": name, "created_at": created, "subject": name}), encoding="utf-8")


def test_pending_messages_stay_in_view_past_the_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MD_HIVE_DIR", str(tmp_path))
    inbox = tmp_path / "agents" / "worker-a" / "inbox"
    # An old pending message must still show when 60 newer handled messages exist.
    _write(inbox, "old-pending.json", "2026-10-01T00:00:00Z")
    for i in range(60):
        _write(inbox / ".done", f"done-{i}.json", f"2026-10-30T00:{i:02d}:00Z")

    rows = Session.inbox(None)["messages"]  # inbox() reads only the hive folder, not session state

    assert len(rows) == 50
    assert rows[0]["id"] == "old-pending.json"
    assert rows[0]["state"] == "pending"
