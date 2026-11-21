"""The kill switch and the confirm gate. Both are shared between threads."""

import threading
from collections.abc import Callable


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

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, bool | None] = {}
        self._shown: dict[str, tuple[str, str]] = {}
        self._on_change = on_change  # told when the list of waiting confirmations changes

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def open(self, call_id: str, name: str = "", preview: str = "") -> None:
        with self._lock:
            self._pending[call_id] = None
            self._shown[call_id] = (name, preview)
        self._changed()

    def waiting(self) -> list[tuple[str, str, str]]:
        """(call id, tool name, preview) for every confirmation still waiting, oldest first (7.19)."""
        with self._lock:
            return [
                (call, *self._shown.get(call, ("", "")))
                for call, decided in self._pending.items()
                if decided is None
            ]

    def decide(self, call_id: str, approve: bool) -> bool:
        """Record the user's answer. False when no confirmation with that id is waiting."""
        with self._lock:
            if call_id not in self._pending or self._pending[call_id] is not None:
                return False  # not waiting: unknown, or already answered
            self._pending[call_id] = approve
        self._changed()
        return True

    def decision(self, call_id: str) -> bool | None:
        with self._lock:
            return self._pending.get(call_id)

    def close(self, call_id: str) -> None:
        with self._lock:
            self._pending.pop(call_id, None)
            self._shown.pop(call_id, None)
        self._changed()


class AskQueue:
    """Questions the assistant put to the user, in the order asked. `None` means still waiting."""

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, str | None] = {}
        self._questions: dict[str, str] = {}
        self._on_change = on_change  # told when the list of waiting questions changes

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def open(self, ask_id: str, question: str = "") -> None:
        with self._lock:
            self._pending[ask_id] = None
            self._questions[ask_id] = question
        self._changed()

    def answer(self, ask_id: str, text: str) -> bool:
        """Record the user's answer. False when no question with that id is waiting."""
        with self._lock:
            if ask_id not in self._pending or self._pending[ask_id] is not None:
                return False  # not waiting: unknown, or already answered
            self._pending[ask_id] = text
        self._changed()
        return True

    def answer_of(self, ask_id: str) -> str | None:
        with self._lock:
            return self._pending.get(ask_id)

    def waiting(self) -> list[tuple[str, str]]:
        """(ask id, question) for every question still waiting, oldest first."""
        with self._lock:
            return [
                (ask_id, self._questions.get(ask_id, ""))
                for ask_id, text in self._pending.items()
                if text is None
            ]

    def close(self, ask_id: str) -> None:
        with self._lock:
            self._pending.pop(ask_id, None)
            self._questions.pop(ask_id, None)
        self._changed()
