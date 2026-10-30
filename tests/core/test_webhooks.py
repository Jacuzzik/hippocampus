from pathlib import Path

import pytest

from core import __main__ as sidecar
from core import webhooks
from core.settings import Settings


def session_at(storage: Path) -> sidecar.Session:
    return sidecar.Session(storage, Settings(), emit=lambda e: None)


def test_webhooks_are_saved_listed_and_deleted(tmp_path: Path) -> None:
    session = session_at(tmp_path)
    assert session.dispatch({"method": "webhooks"}) == {"webhooks": []}
    saved = session.dispatch({"method": "save_webhook", "name": " Nightly ", "kind": "link_check"})
    hook_id = saved["webhooks"][0]["id"]
    assert saved["webhooks"] == [{"id": hook_id, "name": "Nightly", "kind": "link_check"}]
    assert session.dispatch({"method": "webhooks"}) == saved  # read back from disk
    gone = session.dispatch({"method": "delete_webhook", "id": hook_id})
    assert gone == {"webhooks": []}


def test_a_bad_webhook_request_is_refused(tmp_path: Path) -> None:
    session = session_at(tmp_path)
    with pytest.raises(ValueError, match="non-empty"):
        session.dispatch({"method": "save_webhook", "name": "  ", "kind": "link_check"})
    with pytest.raises(ValueError, match="must be one of"):
        session.dispatch({"method": "save_webhook", "name": "x", "kind": "shell"})
    with pytest.raises(ValueError, match="no webhook"):
        session.dispatch({"method": "delete_webhook", "id": "missing"})


def test_running_a_webhook_needs_approval_and_runs_its_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = session_at(tmp_path)
    hook_id = session.dispatch({"method": "save_webhook", "name": "Check", "kind": "link_check"})[
        "webhooks"
    ][0]["id"]
    with pytest.raises(ValueError, match="approval"):
        session.dispatch({"method": "run_webhook", "id": hook_id})
    monkeypatch.setattr(session, "_link_check", lambda: "Check: 0 broken links")
    reply = session.dispatch({"method": "run_webhook", "id": hook_id, "approve": True})
    assert reply == {"result": "Check: 0 broken links"}


def test_a_webhook_file_with_an_unknown_kind_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "webhooks.json"
    path.write_text('[{"id": "a", "name": "x", "kind": "shell"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="known"):
        webhooks.load(path)
