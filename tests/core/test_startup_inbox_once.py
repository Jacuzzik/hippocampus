from pathlib import Path
from typing import Any

from core import __main__ as sidecar
from core.settings import Settings


class FakeTerminals:
    """Stands in for the real terminals: the first start launches, later ones reattach."""

    def __init__(self) -> None:
        self.starts = 0

    def start(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.starts += 1
        if self.starts == 1:
            return {"running": True, "replay": ""}
        return {"running": True, "reattached": True, "replay": ""}


def test_the_start_up_inbox_is_queued_for_a_new_cli_only(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    session.terminals = FakeTerminals()  # type: ignore[assignment]
    request = {
        "method": "terminal_start",
        "agent": "ada",
        "provider": "claude",
        "rows": 24,
        "cols": 80,
    }

    session.dispatch(request)
    assert "ada" in session.inbox_pending  # a CLI that has just started gets its inbox

    session.inbox_pending.clear()  # the delivery loop sent it
    reopened = session.dispatch(request)
    assert reopened["reattached"] is True
    assert session.inbox_pending == {}  # reopening the window does not send it again
