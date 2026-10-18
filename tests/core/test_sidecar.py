import json
import subprocess
import sys

from core import __version__


def run_core(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "core", *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_version_flag() -> None:
    result = run_core("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


def test_serve_announces_ready_and_exits_on_stdin_eof() -> None:
    result = run_core("serve")
    assert result.returncode == 0
    first_line = result.stdout.splitlines()[0]
    assert json.loads(first_line) == {"status": "ready", "version": __version__}


def test_command_is_required() -> None:
    result = run_core()
    assert result.returncode != 0
