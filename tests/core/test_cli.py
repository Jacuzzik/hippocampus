import json
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

import core
from core.__main__ import DEFAULT_STORAGE
from core.vault import index_path_for

PROJECT_ROOT = Path(core.__file__).resolve().parent.parent


def run_core(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "core", *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def has_note(db: Path, path: str) -> bool:
    if not db.exists():
        return False
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        found = conn.execute("SELECT 1 FROM notes WHERE path = ?", (path,)).fetchone()
    conn.close()
    return found is not None


def test_default_storage_is_under_the_project() -> None:
    assert DEFAULT_STORAGE == PROJECT_ROOT / "storage"


def test_index(sample_vault: tuple[Path, dict[str, Any]], storage: Path) -> None:
    vault, manifest = sample_vault
    result = run_core("index", str(vault), "--storage", str(storage))
    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout)
    assert status["status"] == "indexed"
    assert status["index"] == str(index_path_for(vault, storage))
    assert {k: status[k] for k in manifest["totals"]} == manifest["totals"]
    assert status["added_files"] == 200
    assert not index_path_for(vault, DEFAULT_STORAGE).exists()

    again = json.loads(run_core("index", str(vault), "--storage", str(storage)).stdout)
    assert (again["added_files"], again["unchanged_files"]) == (0, 200)


def test_index_missing_vault(tmp_path: Path) -> None:
    result = run_core("index", str(tmp_path / "nope"), "--storage", str(tmp_path / "s"))
    assert result.returncode == 2
    assert "vault folder not found" in result.stderr
    assert not (tmp_path / "s").exists()


@pytest.mark.parametrize("stop", ["stdin", "sigint", "sigterm"])
def test_watch(sample_vault: tuple[Path, dict[str, Any]], storage: Path, stop: str) -> None:
    vault, manifest = sample_vault
    proc = subprocess.Popen(
        [sys.executable, "-m", "core", "watch", str(vault), "--storage", str(storage)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None and proc.stdin is not None
        status = json.loads(proc.stdout.readline())
        assert status["status"] == "watching"
        assert status["notes"] == manifest["totals"]["notes"]

        (vault / "live.md").write_text("hello", encoding="utf-8")
        db = Path(status["index"])
        deadline = time.monotonic() + 5
        while not has_note(db, "live.md"):
            assert time.monotonic() < deadline, "watch did not index the new note"
            time.sleep(0.05)

        if stop == "stdin":
            proc.stdin.close()
        else:
            proc.send_signal(signal.SIGINT if stop == "sigint" else signal.SIGTERM)
        assert proc.wait(timeout=5) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert proc.stderr is not None
    assert "Stopped watching" in proc.stderr.read()
