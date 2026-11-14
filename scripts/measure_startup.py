"""Measure how long the backend takes to answer its first call and how much memory it holds then.

Run: uv run python scripts/measure_startup.py
Writes docs/perf/<version>.json, one file per release, so a later release can be compared with it.
Linux only for the memory number (it reads /proc); elsewhere memory is left out.
"""

import json
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import __version__  # noqa: E402

RUNS = 3


def memory_mb(pid: int) -> float | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None


def one_run() -> tuple[float, float | None]:
    with tempfile.TemporaryDirectory() as storage:
        began = time.monotonic()
        backend = subprocess.Popen(
            [sys.executable, "-m", "core", "serve", "--storage", storage],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        try:
            assert backend.stdin and backend.stdout
            backend.stdin.write(json.dumps({"id": 1, "method": "system"}) + "\n")
            backend.stdin.flush()
            for line in backend.stdout:
                if json.loads(line).get("id") == 1:
                    break
            took = time.monotonic() - began
            return round(took * 1000), memory_mb(backend.pid)
        finally:
            backend.kill()
            backend.wait()


def main() -> None:
    runs = [one_run() for _ in range(RUNS)]
    times = sorted(ms for ms, _ in runs)
    memory = [mb for _, mb in runs if mb is not None]
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    result = {
        "version": __version__,
        "commit": commit,
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "platform": sys.platform,
        "backend_first_answer_ms": {"median": times[len(times) // 2], "runs": times},
        "backend_memory_mb": max(memory) if memory else None,
    }
    out = ROOT / "docs" / "perf" / f"{__version__}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
