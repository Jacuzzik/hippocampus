import json
import subprocess
import sys
from pathlib import Path

from core.system_stats import SystemStats, cpu_percent


def test_cpu_percent_is_the_busy_share_between_two_samples() -> None:
    # 300 busy and 100 idle jiffies passed: 75% busy.
    assert cpu_percent((1000, 5000), (1300, 5400)) == 75.0
    assert cpu_percent((1000, 5000), (1000, 5000)) == 0.0


def test_read_gives_three_percentages_in_range(tmp_path: Path) -> None:
    stats = SystemStats().read(tmp_path)
    assert set(stats) == {"cpu", "ram", "disk"}
    assert all(0 <= value <= 100 for value in stats.values())


def test_serve_answers_system_with_the_three_numbers(storage: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "core", "serve", "--storage", str(storage)],
        input='{"id": 7, "method": "system"}\n',
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    answer = json.loads(result.stdout.splitlines()[-1])
    assert answer["id"] == 7
    assert set(answer["result"]) == {"cpu", "ram", "disk"}
