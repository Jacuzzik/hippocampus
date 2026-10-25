"""The kill switch and the confirm gate. Both are shared between threads."""

import threading


class Stopped(Exception):
    """Raised inside the assistant loop once the kill switch is set."""


class KillSwitch:
    def __init__(self) -> None:
        self._event = threading.Event()

    def trigger(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    def check(self) -> None:
        if self._event.is_set():
            raise Stopped("stopped by the kill switch")


class ConfirmGate:
    """Confirmations waiting for the user. `None` means still waiting."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, bool | None] = {}

    def open(self, call_id: str) -> None:
        with self._lock:
            self._pending[call_id] = None

    def decide(self, call_id: str, approve: bool) -> bool:
        """Record the user's answer. False when no confirmation with that id is waiting."""
        with self._lock:
            if call_id not in self._pending or self._pending[call_id] is not None:
                return False  # not waiting: unknown, or already answered
            self._pending[call_id] = approve
            return True

    def decision(self, call_id: str) -> bool | None:
        with self._lock:
            return self._pending.get(call_id)

    def close(self, call_id: str) -> None:
        with self._lock:
            self._pending.pop(call_id, None)
