"""Soak test: watch the running app for hours and catch slow leaks (memory, CPU, open files, log size).

Start the app, start three agents, then run:
    uv run python scripts/soak.py                 # 8 hours, one sample a minute
    uv run python scripts/soak.py --hours 0.1 --every 10   # a quick try

It only reads /proc and file sizes (Linux), so it costs almost nothing. Every sample goes to a CSV file;
at the end it prints a verdict. It counts the app, its backend and every process they started (the agents).
"""

import argparse
import csv
import os
import time
from datetime import datetime
from pathlib import Path

NAMES = ("hippocampus",)  # the app and its backend both carry this in their command line
LOG_DIRS = (
    Path.home() / ".local/share/dev.hippocampus.desktop",
    Path.home() / ".local/share/hippocampus",
)
# Limits for the verdict: memory may not grow more than this per hour after the first half hour,
# and the logs may not pass this size (the backend log rotates at 4 MB in total).
MAX_MB_PER_HOUR = 50.0
MAX_LOG_MB = 50.0
TICK = os.sysconf("SC_CLK_TCK")


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def roots() -> set[int]:
    found = set()
    for pid in filter(str.isdigit, os.listdir("/proc")):
        cmd = _read(f"/proc/{pid}/cmdline").replace("\0", " ")
        if any(n in cmd for n in NAMES) and "soak.py" not in cmd:
            found.add(int(pid))
    return found


def family(start: set[int]) -> set[int]:
    """The app's processes and all their children, found through each process's parent id."""
    parent = {}
    for pid in filter(str.isdigit, os.listdir("/proc")):
        stat = _read(f"/proc/{pid}/stat")
        if stat:
            parent[int(pid)] = int(stat.rsplit(")", 1)[1].split()[1])
    tree, grew = set(start), True
    while grew:
        more = {p for p, pp in parent.items() if pp in tree and p not in tree}
        tree |= more
        grew = bool(more)
    return tree


def sample(pids: set[int]) -> dict[str, float]:
    rss_kb = cpu_ticks = fds = threads = 0
    for pid in pids:
        for line in _read(f"/proc/{pid}/status").splitlines():
            if line.startswith("VmRSS:"):
                rss_kb += int(line.split()[1])
            elif line.startswith("Threads:"):
                threads += int(line.split()[1])
        stat = _read(f"/proc/{pid}/stat")
        if stat:
            fields = stat.rsplit(")", 1)[1].split()
            cpu_ticks += int(fields[11]) + int(fields[12])  # user + system time
        try:
            fds += len(os.listdir(f"/proc/{pid}/fd"))
        except OSError:
            pass
    logs = sum(
        f.stat().st_size
        for d in LOG_DIRS
        if d.is_dir()
        for f in d.rglob("*")
        if f.suffix in (".log", ".jsonl") and f.is_file()
    )
    return {
        "processes": len(pids),
        "memory_mb": round(rss_kb / 1024, 1),
        "cpu_s": round(cpu_ticks / TICK, 1),
        "open_files": fds,
        "threads": threads,
        "logs_mb": round(logs / 1e6, 2),
    }


def verdict(rows: list[dict[str, float]], every: float) -> list[str]:
    problems = []
    warm = int(1800 / every)  # skip the first half hour while caches fill
    tail = rows[warm:] if len(rows) > warm + 2 else rows
    hours = (len(tail) - 1) * every / 3600
    if hours > 0:
        growth = (tail[-1]["memory_mb"] - tail[0]["memory_mb"]) / hours
        if growth > MAX_MB_PER_HOUR:
            problems.append(f"memory grew {growth:.0f} MB an hour (limit {MAX_MB_PER_HOUR:.0f})")
        files = tail[-1]["open_files"] - tail[0]["open_files"]
        if files > 50:
            problems.append(f"open files rose by {files}: something is not closing them")
    if rows[-1]["logs_mb"] > MAX_LOG_MB:
        problems.append(f"logs reached {rows[-1]['logs_mb']} MB (limit {MAX_LOG_MB:.0f})")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hours", type=float, default=8.0)
    ap.add_argument("--every", type=float, default=60.0, help="seconds between samples")
    ap.add_argument("--out", type=Path, default=Path(f"soak-{datetime.now():%Y%m%d-%H%M}.csv"))
    args = ap.parse_args()
    if not roots():
        print("Hippocampus is not running. Start it (and three agents) first.")
        return 2
    rows: list[dict[str, float]] = []
    end = time.monotonic() + args.hours * 3600
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = None
        while time.monotonic() < end:
            alive = roots()
            if not alive:
                print("The app stopped during the soak test.")
                rows.append({"crashed": 1})
                break
            row = {"time": datetime.now().isoformat(timespec="seconds"), **sample(family(alive))}
            writer = writer or csv.DictWriter(f, fieldnames=list(row))
            if not rows:
                writer.writeheader()
            writer.writerow(row)
            f.flush()
            rows.append(row)
            time.sleep(args.every)
    if not rows or "crashed" in rows[-1]:
        return 1
    first, last = rows[0], rows[-1]
    print(f"{len(rows)} samples in {args.out}")
    for key in ("processes", "memory_mb", "open_files", "threads", "logs_mb"):
        print(f"  {key:11} {first[key]} -> {last[key]} (peak {max(r[key] for r in rows)})")
    problems = verdict(rows, args.every)
    print("PASS" if not problems else "FAIL\n  " + "\n  ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
