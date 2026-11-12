"""The backend's own log file: one place to read what the backend did, with keys masked.

The file sits under the app's storage folder and rotates, so it cannot fill the disk.
"""

import logging
import re
from collections import deque
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

FOLDER = "logs"
FILE = "backend.log"
MAX_BYTES = 1_000_000
BACKUPS = 3
TAIL_MAX = 1000

# Shapes of secrets that must never reach a log line: provider keys, Slack and GitHub tokens, bearer headers.
_SECRETS = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|xox[abpors]-[A-Za-z0-9-]{8,}|gh[pousr]_[A-Za-z0-9]{12,}|AIza[0-9A-Za-z_-]{20,}"
    r"|(?i:bearer)\s+[A-Za-z0-9._~+/=-]{12,})"
)


def mask(text: str) -> str:
    """The same text with anything that looks like a key replaced by [key hidden]."""
    return _SECRETS.sub("[key hidden]", text)


class _MaskKeys(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask(record.getMessage())
        record.args = None
        return True


def path(storage: Path) -> Path:
    return storage / FOLDER / FILE


def attach(storage: Path, level: int = logging.INFO) -> Callable[[], None]:
    """Send every backend log line to the rotating file too. Returns the function that undoes it."""
    file = path(storage)
    file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(file, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(_MaskKeys())
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    def detach() -> None:
        root.removeHandler(handler)
        handler.close()

    return detach


def tail(storage: Path, limit: int = 200) -> list[str]:
    """The newest `limit` lines of the log, oldest first. An unread or missing file gives no lines."""
    limit = max(1, min(int(limit), TAIL_MAX))
    try:
        with path(storage).open(encoding="utf-8", errors="replace") as handle:
            return [line.rstrip("\n") for line in deque(handle, maxlen=limit)]
    except OSError:
        return []
