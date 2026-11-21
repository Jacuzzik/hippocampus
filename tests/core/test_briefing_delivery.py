"""The card can say how an agent's briefing reached its CLI, and when it did not."""

import os
import threading
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
    monkeypatch.setattr(terminal, "BRIEFING_REACT_S", 0.3)
    monkeypatch.setattr(terminal, "BRIEFING_RETRY_S", 0.0)
    return Terminals(emit=lambda e: None)


def _react_later(terms: Terminals, after: float) -> None:
    """The CLI answers `after` seconds from now, as a real one draws something when it takes a line."""
    threading.Timer(after, lambda: terms.last_output.__setitem__("ada", time.time())).start()


def test_a_typed_pointer_is_marked_delivered(monkeypatch) -> None:
    terms = _terms(monkeypatch)
    read_end, write_end = os.pipe()
    proc = FakeProc(None)
    terms.procs["ada"] = (proc, write_end)  # type: ignore[assignment]
    terms.last_output["ada"] = time.time()
    _react_later(terms, 0.05)
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


def test_a_cli_that_never_reacts_gets_the_pointer_again_then_a_warning(monkeypatch) -> None:
    terms = _terms(monkeypatch)
    read_end, write_end = os.pipe()
    proc = FakeProc(None)
    terms.procs["ada"] = (proc, write_end)  # type: ignore[assignment]
    terms.last_output["ada"] = time.time()
    terms._send_briefing("ada", proc, write_end, "/tmp/briefings/ada.md")  # type: ignore[arg-type]
    assert terms.briefing_delivery["ada"].startswith("Typed, but the CLI did not react")
    assert os.read(read_end, 65536).count(b"/tmp/briefings/ada.md") == terminal.BRIEFING_TRIES
    os.close(read_end)
    os.close(write_end)


def test_a_slow_cli_that_reacts_after_the_second_try_is_delivered(monkeypatch) -> None:
    terms = _terms(monkeypatch)
    read_end, write_end = os.pipe()
    proc = FakeProc(None)
    terms.procs["ada"] = (proc, write_end)  # type: ignore[assignment]
    terms.last_output["ada"] = time.time()
    _react_later(terms, 0.4)  # after the first 0.3 s wait, during the second
    terms._send_briefing("ada", proc, write_end, "/tmp/briefings/ada.md")  # type: ignore[arg-type]
    assert terms.briefing_delivery["ada"] == "Delivered: typed into the terminal (took 2 tries)"
    os.close(read_end)
    os.close(write_end)


def test_each_provider_has_one_delivery_path_in_its_command(monkeypatch, tmp_path) -> None:
    """8.02: Claude takes the briefing as a system prompt file, OpenCode as its first prompt, the rest are
    typed in (so their command line carries no briefing)."""
    monkeypatch.setattr(terminal.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(terminal.cli_sessions, "FILE", tmp_path / "sessions.json")
    brief = "/tmp/briefings/ada.md"
    claude = terminal._command("ada", "claude", briefing=brief)
    assert claude[claude.index("--append-system-prompt-file") + 1] == brief
    opencode = terminal._command("ada", "gemini", "gemini-2.5-pro", briefing=brief)
    assert brief in opencode[opencode.index("--prompt") + 1]
    for provider in ("codex", "gemini-cli"):
        argv = terminal._command("ada", provider, "m", briefing=brief)
        assert not any(brief in part for part in argv), provider
