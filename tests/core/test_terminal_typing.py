import threading
import time
from pathlib import Path

from core import terminal
from core.terminal import Terminals


class Recorder(Terminals):
    """Terminals with the pty write replaced by a list, so the order of typed bytes can be read."""

    def __init__(self) -> None:
        super().__init__(emit=lambda e: None)
        self.typed: list[str] = []
        self.status = "Idle"

    def write(self, agent: str, data: str) -> None:
        self.typed.append(data)

    def info(self, agent: str):  # type: ignore[override]
        return {"status": self.status}


def test_two_lines_typed_at_once_do_not_mix(monkeypatch) -> None:
    monkeypatch.setattr(terminal, "SUBMIT_DELAY_S", 0.05)
    terms = Recorder()
    workers = [threading.Thread(target=terms.send_line, args=("ada", text)) for text in ("inbox text", "/remote-control x")]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    # Each line is followed by its own Enter before the next line starts.
    assert terms.typed[1] == "\r" and terms.typed[3] == "\r"
    assert {terms.typed[0], terms.typed[2]} == {"inbox text", "/remote-control x"}


def test_a_quiet_line_waits_while_the_cli_is_busy_or_was_just_typed_into(monkeypatch) -> None:
    monkeypatch.setattr(terminal, "SUBMIT_DELAY_S", 0.0)
    monkeypatch.setattr(terminal, "TYPE_GAP_S", 0.2)
    terms = Recorder()
    terms.status = "Working"
    assert terms.send_line_when_quiet("ada", "/remote-control x") is False
    terms.status = "Idle"
    terms.send_line("ada", "inbox text")
    assert terms.send_line_when_quiet("ada", "/remote-control x") is False  # typed a moment ago
    time.sleep(0.25)
    assert terms.send_line_when_quiet("ada", "/remote-control x") is True
    assert terms.typed == ["inbox text", "\r", "/remote-control x", "\r"]
