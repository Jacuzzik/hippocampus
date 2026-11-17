"""The soak tool's verdict: steady numbers pass, a leak or a log flood fails."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "soak", Path(__file__).resolve().parent.parent / "scripts" / "soak.py"
)
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)  # type: ignore[union-attr]


def rows(memory: list[float], files: int = 10, logs: float = 1.0) -> list[dict[str, float]]:
    return [{"memory_mb": m, "open_files": files, "logs_mb": logs} for m in memory]


def test_steady_memory_passes() -> None:
    assert soak.verdict(rows([300.0] * 120), every=60) == []


def test_memory_that_keeps_growing_fails() -> None:
    [problem] = soak.verdict(rows([300.0 + 2 * i for i in range(120)]), every=60)
    assert "memory grew" in problem


def test_a_log_flood_fails() -> None:
    [problem] = soak.verdict(rows([300.0] * 10, logs=80.0), every=60)
    assert "logs reached" in problem


def test_this_process_tree_is_found() -> None:
    import os

    assert os.getpid() in soak.family({os.getppid()})
