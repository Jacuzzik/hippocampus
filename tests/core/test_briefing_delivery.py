"""The card can say how an agent's briefing reached its CLI, and when it did not."""

import os
import time

from core import terminal
from core.terminal import Terminals


class FakeProc:
    def __init__(self, code: int | None) -> None:
        self.code = code

    def poll(self) -> int | None:
        return self.code


def _terms(monkeypatch) -> Terminals:
    monkeypatch.setattr(terminal, "BRIEFING_DELAY_S", 0.0)
    monkeypatch.setattr(terminal, "SUBMIT_DELAY_S", 0.0)
    return Terminals(emit=lambda e: None)


def test_a_typed_pointer_is_marked_delivered(monkeypatch) -> None:
    terms = _terms(monkeypatch)
    read_end, write_end = os.pipe()
    proc = FakeProc(None)
    terms.procs["ada"] = (proc, write_end)  # type: ignore[assignment]
    terms.last_output["ada"] = time.time()
    terms._send_briefing("ada", proc, write_end, "/tmp/briefings/ada.md")  # type: ignore[arg-type]
    assert terms.briefing_delivery["ada"] == "Delivered: typed into the terminal"
    assert b"/tmp/briefings/ada.md" in os.read(read_end, 4096)
    os.close(read_end)
    os.close(write_end)


def test_a_cli_that_stopped_first_is_marked_not_delivered(monkeypatch) -> None:
    terms = _terms(monkeypatch)
    proc = FakeProc(1)
    terms.procs["ada"] = (proc, 99)  # type: ignore[assignment]
    terms._send_briefing("ada", proc, 99, "/tmp/briefings/ada.md")  # type: ignore[arg-type]
    assert terms.briefing_delivery["ada"] == "Not delivered: the CLI stopped first"


def test_a_failed_write_is_marked_not_delivered(monkeypatch) -> None:
    terms = _terms(monkeypatch)
    read_end, write_end = os.pipe()
    os.close(read_end)
    os.close(write_end)  # writing to a closed descriptor fails
    proc = FakeProc(None)
    terms.procs["ada"] = (proc, write_end)  # type: ignore[assignment]
    terms.last_output["ada"] = time.time()
    terms._send_briefing("ada", proc, write_end, "/tmp/briefings/ada.md")  # type: ignore[arg-type]
    assert terms.briefing_delivery["ada"] == "Not delivered: typing it in failed"
    assert terms.info("ada")["delivery"] == "Not delivered: typing it in failed"
