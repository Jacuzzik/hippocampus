"""One list of checks that says whether the app has what it needs, and what to do about each gap.

Every check is a plain row: a name, a state ("ok", "warn" or "bad"), what was found, and the next step
when there is one. Nothing here changes anything; it only looks.
"""

import shutil
from pathlib import Path
from typing import Any

Row = dict[str, Any]

DISK_FREE_MIN_GB = 2.0


def row(name: str, state: str, found: str, fix: str = "") -> Row:
    return {"name": name, "state": state, "found": found, "fix": fix}


def check_vault(vault: Path | None, notes: int | None) -> Row:
    if vault is None:
        return row(
            "Vault",
            "bad",
            "No vault folder is set.",
            "Settings > General: choose your notes folder.",
        )
    if not vault.is_dir():
        return row(
            "Vault",
            "bad",
            f"The folder {vault} does not exist.",
            "Settings > General: choose another folder.",
        )
    if notes is None:
        return row(
            "Vault",
            "warn",
            f"{vault} is set but not open.",
            "Reopen the app, or choose the folder again.",
        )
    return row("Vault", "ok", f"{notes} notes in {vault}.")


def check_disk(storage: Path) -> Row:
    try:
        free = shutil.disk_usage(storage if storage.exists() else storage.parent).free / 1e9
    except OSError as cause:
        return row("Disk space", "warn", f"Could not read the disk: {cause}.")
    if free < DISK_FREE_MIN_GB:
        return row(
            "Disk space",
            "bad",
            f"{free:.1f} GB free.",
            "Free some space: the app keeps its index and logs here.",
        )
    return row("Disk space", "ok", f"{free:.1f} GB free.")


def check_clis(clis: list[dict[str, Any]]) -> list[Row]:
    """One row per agent program. Not having one is fine; having none at all is not."""
    rows = []
    for cli in clis:
        name = f"{cli['label']} program"
        if not cli["installed"]:
            rows.append(row(name, "warn", "Not installed.", cli["steps"]))
        elif cli["logged_in"] is False:
            rows.append(row(name, "bad", "Installed, but not signed in.", cli["steps"]))
        elif cli["logged_in"] is None:
            rows.append(row(name, "ok", "Installed. Sign-in cannot be checked from here."))
        else:
            rows.append(row(name, "ok", "Installed and signed in."))
    if clis and not any(cli["installed"] for cli in clis):
        rows.insert(
            0,
            row(
                "Agent programs",
                "bad",
                "No agent program is installed, so no agent can run.",
                "Install Claude Code, then run `claude` once in a terminal to sign in.",
            ),
        )
    return rows


def check_sandbox(available: bool, shell_on: bool) -> Row:
    if not available:
        return row(
            "Agent sandbox",
            "warn",
            "bubblewrap cannot start here.",
            "Install bubblewrap (bwrap) to give every agent a shell safely. Without it only the main agent has one.",
        )
    if shell_on:
        return row("Agent sandbox", "ok", "Available, and on for agents that run Claude Code.")
    return row(
        "Agent sandbox",
        "ok",
        "Available, and off.",
        "Settings > Agents: turn on 'Shell for every agent' if you want agents to run shell commands.",
    )


def check_log(path: Path) -> Row:
    if path.is_file():
        return row("Backend log", "ok", f"Written to {path}.")
    return row(
        "Backend log", "warn", "No log file yet.", "It appears after the backend's first log line."
    )


def summary(rows: list[Row]) -> dict[str, int]:
    return {state: sum(1 for r in rows if r["state"] == state) for state in ("ok", "warn", "bad")}
