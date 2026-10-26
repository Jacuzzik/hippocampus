import asyncio
import io
import json
import queue
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from ai.providers.base import Reply, ToolCall
from ai.router import Router
from core import __main__ as sidecar
from core.settings import Settings


class Scripted:
    name = "scripted"

    def __init__(self, *steps: Reply | Callable[[], Awaitable[Reply]]) -> None:
        self.steps = list(steps)
        self.called = threading.Event()

    async def chat(self, messages: list[dict[str, Any]], tools: list[Any]) -> Reply:
        self.called.set()
        step = self.steps.pop(0)
        if callable(step):
            return await step()
        return step


def feed(lines: "queue.Queue[str | None]") -> Iterator[str]:
    while (line := lines.get()) is not None:
        yield line


def run_serve(
    storage: Path,
    provider: Scripted,
    lines: "queue.Queue[str | None]",
    out: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> threading.Thread:
    monkeypatch.setattr(sidecar, "build_router", lambda settings, key: Router(None, provider))
    thread = threading.Thread(
        target=sidecar.serve,
        kwargs={"storage": storage, "lines": feed(lines), "out": out, "settings": Settings()},
    )
    thread.start()
    return thread


def answers(out: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.getvalue().splitlines()]


def wait_for(
    out: io.StringIO, predicate: Callable[[dict[str, Any]], bool], timeout: float = 5.0
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for item in answers(out):
            if predicate(item):
                return item
        time.sleep(0.01)
    raise AssertionError(f"no matching line in {out.getvalue()!r}")


def test_chat_answers_and_stays_out_of_the_way_of_graph(
    sample_vault: tuple[Path, dict[str, Any]], storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, _ = sample_vault
    lines: queue.Queue[str | None] = queue.Queue()
    out = io.StringIO()
    thread = run_serve(storage, Scripted(Reply("hello from the test")), lines, out, monkeypatch)
    lines.put(json.dumps({"id": 1, "method": "open", "vault": str(vault)}))
    lines.put(json.dumps({"id": 2, "method": "chat", "chat": 2, "text": "hi"}))
    lines.put(json.dumps({"id": 3, "method": "graph"}))
    chat = wait_for(out, lambda a: a.get("id") == 2)
    graph = wait_for(out, lambda a: a.get("id") == 3)
    lines.put(None)
    thread.join(timeout=10)
    assert chat["result"] == {"reply": "hello from the test", "stopped": False}
    assert graph["result"]["nodes"]
    assert answers(out)[0] == {"status": "ready", "version": sidecar.__version__}


def test_write_needs_confirm_through_the_protocol(
    sample_vault: tuple[Path, dict[str, Any]], storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, _ = sample_vault
    provider = Scripted(
        Reply(
            "", [ToolCall("call-1", "create_note", {"path": "new/idea.md", "content": "# Idea\n"})]
        ),
        Reply("I created the note"),
    )
    lines: queue.Queue[str | None] = queue.Queue()
    out = io.StringIO()
    thread = run_serve(storage, provider, lines, out, monkeypatch)
    lines.put(json.dumps({"id": 1, "method": "open", "vault": str(vault)}))
    lines.put(json.dumps({"id": 2, "method": "chat", "chat": 2, "text": "make a note"}))
    card = wait_for(out, lambda a: a.get("event") == "confirm")
    assert card["preview"].startswith("--- /dev/null") and card["call"] == "call-1"
    assert not (vault / "new" / "idea.md").exists()
    lines.put(json.dumps({"method": "confirm", "call": "call-1", "approve": True}))
    chat = wait_for(out, lambda a: a.get("id") == 2)
    lines.put(None)
    thread.join(timeout=10)
    assert chat["result"]["reply"] == "I created the note"
    assert (vault / "new" / "idea.md").read_text(encoding="utf-8") == "# Idea\n"


def test_stop_halts_a_running_chat(storage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow() -> Reply:
        await asyncio.sleep(30)
        return Reply("never")

    provider = Scripted(slow)
    lines: queue.Queue[str | None] = queue.Queue()
    out = io.StringIO()
    thread = run_serve(storage, provider, lines, out, monkeypatch)
    lines.put(json.dumps({"id": 7, "method": "chat", "text": "long task"}))
    assert provider.called.wait(5)
    started = time.monotonic()
    lines.put(json.dumps({"id": 8, "method": "stop"}))
    chat = wait_for(out, lambda a: a.get("id") == 7)
    assert time.monotonic() - started < 1.0
    assert chat["result"] == {"reply": "", "stopped": True}
    lines.put(None)
    thread.join(timeout=10)


def test_chat_needs_text_and_confirm_needs_a_waiting_call(storage: Path) -> None:
    session = sidecar.Session(storage, Settings())
    with pytest.raises(ValueError, match="non-empty"):
        session.dispatch({"method": "chat", "text": "  "})
    with pytest.raises(ValueError, match="no confirmation"):
        session.dispatch({"method": "confirm", "call": "nope", "approve": True})
    session.close()


def test_answer_needs_a_waiting_question(storage: Path) -> None:
    session = sidecar.Session(storage, Settings())
    with pytest.raises(ValueError, match="no question"):
        session.dispatch({"method": "answer", "call": "nope", "text": "x"})
    session.close()
