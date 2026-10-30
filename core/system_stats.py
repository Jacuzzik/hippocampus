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


def _ram_percent() -> float:
    info = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        info[key] = int(rest.split()[0])
    total = info["MemTotal"]
    return 100 * (total - info["MemAvailable"]) / total


def _disk_percent(folder: Path) -> float:
    while not folder.exists() and folder != folder.parent:  # storage may not be created yet
        folder = folder.parent
    st = os.statvfs(folder)
    used = st.f_blocks - st.f_bfree
    # The same formula `df` prints as Use%: used over the space a non-root user can use.
    return 100 * used / (used + st.f_bavail or 1)


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
        return {
            "cpu": round(cpu, 1),
            "ram": round(_ram_percent(), 1),
            "disk": round(_disk_percent(folder), 1),
        }
