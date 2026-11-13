"""A CLI that ends with an error we did not ask for leaves a crash record; one we stopped does not."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.terminal import Terminals

pty = pytest.importorskip("pty", exc_type=ImportError)  # Unix only


def run_pump(tmp_path: Path, code: int, stopped: bool) -> list[tuple[str, int]]:
    crashes: list[tuple[str, int]] = []
    terminals = Terminals(lambda event: None, tmp_path, lambda agent, c: crashes.append((agent, c)))
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        [sys.executable, "-c", f"raise SystemExit({code})"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
    )
    os.close(slave)
    if stopped:
        terminals.stopping.add("a1")
    terminals._pump("a1", proc, master)
    return crashes


def test_a_failed_exit_is_recorded(tmp_path: Path) -> None:
    assert run_pump(tmp_path, 3, stopped=False) == [("a1", 3)]


def test_a_clean_exit_or_a_stop_we_asked_for_is_not(tmp_path: Path) -> None:
    assert run_pump(tmp_path, 0, stopped=False) == []
    assert run_pump(tmp_path, 3, stopped=True) == []
