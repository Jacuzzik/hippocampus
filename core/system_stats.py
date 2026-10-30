"""Host CPU, RAM and disk use, read only. Linux only: it reads /proc and calls statvfs."""

from __future__ import annotations

import os
import time
from pathlib import Path


def _cpu_times() -> tuple[int, int]:
    """Busy and total jiffies from the first line of /proc/stat (idle includes iowait)."""
    fields = [int(value) for value in Path("/proc/stat").read_text().split("\n", 1)[0].split()[1:8]]
    idle = fields[3] + fields[4]
    total = sum(fields)
    return total - idle, total


def cpu_percent(prev: tuple[int, int], now: tuple[int, int]) -> float:
    busy, total = now[0] - prev[0], now[1] - prev[1]
    return 100 * busy / total if total > 0 else 0.0


def _meminfo() -> dict[str, int]:
    info = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        info[key] = int(rest.split()[0])
    return info


def _ram_percent(info: dict[str, int]) -> float:
    total = info["MemTotal"]
    return 100 * (total - info["MemAvailable"]) / total


def _swap_percent(info: dict[str, int]) -> float:
    total = info["SwapTotal"]  # no swap configured: 0% used, not a division by zero
    return 100 * (total - info["SwapFree"]) / total if total else 0.0


def _disk_folder(folder: Path) -> Path:
    while not folder.exists() and folder != folder.parent:  # storage may not be created yet
        folder = folder.parent
    return folder


def _disk_percent(folder: Path) -> float:
    st = os.statvfs(_disk_folder(folder))
    used = st.f_blocks - st.f_bfree
    # The same formula `df` prints as Use%: used over the space a non-root user can use.
    return 100 * used / (used + st.f_bavail or 1)


def _disk_free_gb(folder: Path) -> float:
    st = os.statvfs(_disk_folder(folder))
    return st.f_bavail * st.f_frsize / 1024**3  # GiB, as `df -h` shows it


class SystemStats:
    """Keeps the last CPU sample, so each read is the busy share since the one before."""

    def __init__(self) -> None:
        self._cpu: tuple[int, int] | None = None

    def read(self, folder: Path) -> dict[str, float]:
        if self._cpu is None:  # first call: sample twice so there is a window to measure
            self._cpu = _cpu_times()
            time.sleep(0.2)
        now = _cpu_times()
        cpu = cpu_percent(self._cpu, now)
        self._cpu = now
        info = _meminfo()
        return {
            "cpu": round(cpu, 1),
            "ram": round(_ram_percent(info), 1),
            "swap": round(_swap_percent(info), 1),
            "disk": round(_disk_percent(folder), 1),
            "disk_free": round(_disk_free_gb(folder), 1),
        }
