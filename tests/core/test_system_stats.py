import json
import subprocess
import sys
from pathlib import Path

from core.system_stats import SystemStats, _swap_percent, cpu_percent


def test_cpu_percent_is_the_busy_share_between_two_samples() -> None:
    # 300 busy and 100 idle jiffies passed: 75% busy.
    assert cpu_percent((1000, 5000), (1300, 5400)) == 75.0
    assert cpu_percent((1000, 5000), (1000, 5000)) == 0.0


def test_swap_percent_is_used_swap_and_zero_without_swap() -> None:
    # 1000 kB of swap with 250 kB free: 75% used. No swap configured: 0%, not an error.
    assert _swap_percent({"SwapTotal": 1000, "SwapFree": 250}) == 75.0
    assert _swap_percent({"SwapTotal": 0, "SwapFree": 0}) == 0.0


def test_read_gives_percentages_in_range_and_disk_free_in_gb(tmp_path: Path) -> None:
    stats = SystemStats().read(tmp_path)
    assert set(stats) == {"cpu", "ram", "swap", "disk", "disk_free"}
    assert all(0 <= stats[key] <= 100 for key in ("cpu", "ram", "swap", "disk"))
    assert stats["disk_free"] >= 0


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
    assert set(answer["result"]) == {"cpu", "ram", "swap", "disk", "disk_free"}
