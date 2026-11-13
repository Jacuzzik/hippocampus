"""Names every part of the session uses: limits, default folders and the prompts typed into terminals."""

import json
import logging
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

# The office task board the Tasks tab reads; MD_TASKS_FILE overrides it.
DEFAULT_TASKS_FILE = "~/.hippocampus/office/tasks.json"
DEFAULT_HIVE_DIR = "~/.hippocampus/office"
# Seconds a terminal must have been running before its waiting inbox messages are typed in.
INBOX_SETTLE_S = 8.0
# How much of a message body is typed into a terminal, and how long a message waits for a busy CLI.
DELIVERY_BODY_MAX = 1500
DELIVERY_MAX_WAIT_S = 120.0

logger = logging.getLogger("hippocampus.core")

DEFAULT_STORAGE = Path(__file__).resolve().parent.parent / "data" / "storage"
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
SCHEDULE_SECONDS = 60
KEYCHAIN_MISSING = (
    "the OS keychain is not available. Install a Secret Service keyring "
    "(for example GNOME Keyring or KWallet), then try again."
)


Emit = Callable[[dict[str, Any]], None]


COMPACT_SAVE_PROMPT = (
    "Before you compact: save your notes and a short summary of today to your note {agent}-PriorityNotes in the vault, "
    "link it from the Summaries note, then reply Saved."
)
COMPACT_PROMPT = (
    "/compact Keep the current task, recent decisions, open questions, and file paths in play. "
    "Drop resolved tangents. Read {agent}-PriorityNotes."
)


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'"{name}" must be a whole number, 0 or more')
    return value


def issues_in(folder: object) -> dict[str, Any]:
    """Open GitHub issues of the repo in a folder, read with the gh CLI the user is logged in to."""
    if not isinstance(folder, str) or not Path(folder).is_dir():
        return {"error": "That folder does not exist."}
    if shutil.which("gh") is None:
        return {"error": "The gh CLI is not installed."}
    try:
        done = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--state",
                "open",
                "--limit",
                "30",
                "--json",
                "number,title,url",
            ],
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": "GitHub took too long to answer."}
    if done.returncode != 0:
        return {"error": done.stderr.strip() or "gh could not list the issues."}
    return {"issues": json.loads(done.stdout or "[]")}
