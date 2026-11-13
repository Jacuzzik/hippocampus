"""A resize must reach the CLI: it runs with no controlling terminal, so the app sends the signal itself."""

import os
import select
import subprocess
import sys

import pytest

from core.terminal import Terminals

# Pseudo-terminals are a Linux and macOS thing; on Windows this file is skipped.
pty = pytest.importorskip("pty", exc_type=ImportError)

CHILD = """
import os, signal, sys, time
def on_change(*_):
    size = os.get_terminal_size(1)
    sys.stdout.write(f"SIZE {size.lines} {size.columns}\\n")
    sys.stdout.flush()
signal.signal(signal.SIGWINCH, on_change)
sys.stdout.write("READY\\n")
sys.stdout.flush()
time.sleep(10)
"""


def _read_until(fd: int, marker: str, seconds: float = 5.0) -> str:
    seen = ""
    while marker not in seen:
        ready, _, _ = select.select([fd], [], [], seconds)
        if not ready:
            break
        seen += os.read(fd, 4096).decode("utf-8", "replace")
    return seen


def test_resize_tells_the_cli_its_new_size() -> None:
    master, slave = pty.openpty()
    Terminals._resize(slave, 24, 80)
    # Started the way the app starts a CLI: its own session, the pseudo-terminal as its input and output.
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
        close_fds=True,
    )
    os.close(slave)
    try:
        assert "READY" in _read_until(master, "READY")
        Terminals._resize_running(proc, master, 30, 62)
        assert "SIZE 30 62" in _read_until(master, "SIZE 30 62")
    finally:
        proc.kill()
        proc.wait()
        os.close(master)


def test_resize_of_a_finished_cli_does_not_raise() -> None:
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        [sys.executable, "-c", "pass"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
    )
    os.close(slave)
    proc.wait()
    try:
        Terminals._resize_running(proc, master, 30, 62)
    finally:
        os.close(master)
