"""The network switch: which directions the app may reach outside this machine.

Off is the default. Model calls are the converse direction, so Off and Listen block them.
"""

import threading

MODES = ("off", "listen", "converse", "open")
_lock = threading.Lock()
_mode = "converse"


def set_mode(mode: str) -> None:
    global _mode
    if mode not in MODES:
        raise ValueError(f"network mode must be one of: {', '.join(MODES)}")
    with _lock:
        _mode = mode


def mode() -> str:
    with _lock:
        return _mode


def allows_model_calls() -> bool:
    return mode() in ("converse", "open")
