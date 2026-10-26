import asyncio
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from ai.agent import Agent, AgentError
from ai.providers.base import ProviderError, Reply, ToolCall
from ai.router import Router
from tools.gate import AskQueue, ConfirmGate, KillSwitch, Stopped
from tools.registry import Tool


class Scripted:
    """A provider that answers from a script; each step is a Reply, or a callable that blocks."""

    name = "scripted"

    def __init__(self, *steps: Reply | Callable[[], Awaitable[Reply]]) -> None:
        self.steps = list(steps)

    async def chat(self, messages: list[dict[str, Any]], tools: list[Any]) -> Reply:
        step = self.steps.pop(0)
        if callable(step):
            return await step()
        return step


def make_agent(
    provider: Scripted, tools: dict[str, Tool]
) -> tuple[Agent, list[dict], KillSwitch, ConfirmGate]:
    events: list[dict] = []
    kill, gate = KillSwitch(), ConfirmGate()
    agent = Agent(Router(None, provider), tools, kill, gate, events.append)
    return agent, events, kill, gate


def write_tool(calls: list[dict]) -> Tool:
    def run(args: dict) -> str:
        calls.append(args)
        return "wrote"

    return Tool("create_note", "write", "", {}, run, preview=lambda a: f"create {a['path']}")


def read_tool(calls: list[dict]) -> Tool:
    def run(args: dict) -> str:
        calls.append(args)
        return "text"

    return Tool("read_note", "read", "", {}, run)


def ask(agent: Agent) -> str:
    return asyncio.run(agent.run("do it"))


def test_read_tools_run_without_confirmation() -> None:
    seen: list[dict] = []
    provider = Scripted(
        Reply("", [ToolCall("c1", "read_note", {"path": "a.md"})]),
        Reply("the note says text"),
    )
    agent, events, _, _ = make_agent(provider, {"read_note": read_tool(seen)})
    assert ask(agent) == "the note says text"
    assert seen == [{"path": "a.md"}]
    assert not [e for e in events if e["event"] == "confirm"]


def test_write_waits_for_approval_and_shows_the_preview() -> None:
    ran: list[dict] = []
    provider = Scripted(
        Reply("", [ToolCall("c1", "create_note", {"path": "x.md"})]),
        Reply("created it"),
    )
    agent, events, _, gate = make_agent(provider, {"create_note": write_tool(ran)})

    def approve_when_asked() -> None:
        while not any(e["event"] == "confirm" for e in events):
            time.sleep(0.01)
        confirm = next(e for e in events if e["event"] == "confirm")
        assert confirm["preview"] == "create x.md" and confirm["tier"] == "write"
        assert gate.decide("c1", True)

    threading.Thread(target=approve_when_asked).start()
    assert ask(agent) == "created it"
    assert ran == [{"path": "x.md"}]


def test_declined_write_does_not_run() -> None:
    ran: list[dict] = []
    provider = Scripted(
        Reply("", [ToolCall("c1", "create_note", {"path": "x.md"})]),
        Reply("ok, not created"),
    )
    agent, events, _, gate = make_agent(provider, {"create_note": write_tool(ran)})

    def decline() -> None:
        while gate.decision("c1") is None and not any(e["event"] == "confirm" for e in events):
            time.sleep(0.01)
        gate.decide("c1", False)

    threading.Thread(target=decline).start()
    assert ask(agent) == "ok, not created"
    assert ran == []
    assert [e["status"] for e in events if e["event"] == "tool"][-1] == "declined"


def test_kill_switch_stops_a_pending_confirmation_within_a_second() -> None:
    ran: list[dict] = []
    provider = Scripted(Reply("", [ToolCall("c1", "create_note", {"path": "x.md"})]))
    agent, events, kill, _ = make_agent(provider, {"create_note": write_tool(ran)})
    killed_at: list[float] = []

    def press_stop() -> None:
        while not any(e["event"] == "confirm" for e in events):
            time.sleep(0.01)
        killed_at.append(time.monotonic())
        kill.trigger()

    threading.Thread(target=press_stop).start()
    with pytest.raises(Stopped):
        ask(agent)
    assert time.monotonic() - killed_at[0] < 1.0
    assert ran == []


def test_kill_switch_stops_a_slow_model_call_within_a_second() -> None:
    async def slow() -> Reply:
        await asyncio.sleep(30)
        return Reply("too late")

    agent, _, kill, _ = make_agent(Scripted(slow), {})
    threading.Timer(0.1, kill.trigger).start()
    started = time.monotonic()
    with pytest.raises(Stopped):
        ask(agent)
    assert time.monotonic() - started < 1.0


def test_kill_switch_is_checked_before_a_tool_runs() -> None:
    seen: list[dict] = []
    provider = Scripted(Reply("", [ToolCall("c1", "read_note", {"path": "a.md"})]))
    agent, _, kill, _ = make_agent(provider, {"read_note": read_tool(seen)})
    kill.trigger()
    with pytest.raises(Stopped):
        ask(agent)
    assert seen == []


def test_tool_errors_go_back_to_the_model() -> None:
    def broken(args: dict) -> str:
        raise ValueError("path leaves the vault")

    provider = Scripted(
        Reply("", [ToolCall("c1", "read_note", {"path": "../x.md"})]),
        Reply("could not read it"),
    )
    agent, events, _, _ = make_agent(
        provider, {"read_note": Tool("read_note", "read", "", {}, broken)}
    )
    assert ask(agent) == "could not read it"
    assert [e["status"] for e in events if e["event"] == "tool"][-1] == "failed"


def test_unknown_tool_and_step_limit() -> None:
    provider = Scripted(Reply("", [ToolCall("c1", "rm_rf", {})]), Reply("sorry"))
    agent, _, _, _ = make_agent(provider, {})
    assert ask(agent) == "sorry"

    loop = [Reply("", [ToolCall(f"c{i}", "nope", {})]) for i in range(20)]
    agent, _, _, _ = make_agent(Scripted(*loop), {})
    with pytest.raises(AgentError):
        ask(agent)


def test_provider_failure_propagates() -> None:
    async def down() -> Reply:
        raise ProviderError("both models are down")

    agent, _, _, _ = make_agent(Scripted(down), {})
    with pytest.raises(ProviderError):
        ask(agent)


def test_gate_decide_only_answers_open_calls() -> None:
    gate = ConfirmGate()
    assert gate.decide("nope", True) is False
    gate.open("c")
    assert gate.decide("c", True) is True
    assert gate.decision("c") is True
    gate.close("c")
    assert gate.decision("c") is None


def test_tool_not_on_the_allowed_list_is_refused() -> None:
    seen: list[dict] = []
    provider = Scripted(
        Reply("", [ToolCall("c1", "read_note", {"path": "a.md"})]),
        Reply("could not read it"),
    )
    tools = {"read_note": read_tool(seen)}
    events: list[dict] = []
    agent = Agent(
        Router(None, provider), tools, KillSwitch(), ConfirmGate(), events.append, allowed={"other"}
    )
    messages: list[dict] = []
    assert asyncio.run(agent.run("read it", messages)) == "could not read it"
    assert seen == []
    assert messages[-2]["content"] == "error: this assistant may not use read_note."


def test_assistant_asks_the_user_and_waits_for_the_answer() -> None:
    asks = AskQueue()
    provider = Scripted(
        Reply("", [ToolCall("q1", "ask_user", {"question": "Which folder?"})]),
        Reply("I will use notes"),
    )
    events: list[dict] = []
    kill = KillSwitch()
    agent = Agent(Router(None, provider), {}, kill, ConfirmGate(), events.append, asks=asks)
    messages: list[dict] = []

    def answer_when_asked() -> None:
        while not any(e["event"] == "ask" for e in events):
            time.sleep(0.01)
        assert [e for e in events if e["event"] == "ask"][0]["question"] == "Which folder?"
        assert asks.waiting() == ["q1"]
        assert asks.answer("q1", "notes")

    threading.Thread(target=answer_when_asked).start()
    assert asyncio.run(agent.run("write a note", messages)) == "I will use notes"
    assert messages[-2] == {
        "role": "tool",
        "tool_call_id": "q1",
        "name": "ask_user",
        "content": "notes",
    }
    assert asks.waiting() == []


def test_stop_ends_a_question_that_is_waiting() -> None:
    asks = AskQueue()
    provider = Scripted(Reply("", [ToolCall("q1", "ask_user", {"question": "Which?"})]))
    kill = KillSwitch()
    events: list[dict] = []

    def stop_when_asked(event: dict) -> None:
        events.append(event)
        if event["event"] == "ask":
            kill.trigger()

    agent = Agent(Router(None, provider), {}, kill, ConfirmGate(), stop_when_asked, asks=asks)
    with pytest.raises(Stopped):
        asyncio.run(agent.run("go"))
    assert asks.waiting() == []


def test_answer_only_fills_a_question_that_is_waiting() -> None:
    asks = AskQueue()
    asks.open("q1")
    assert asks.answer("q1", "first")
    assert not asks.answer("q1", "second")
    assert not asks.answer("missing", "x")
    assert asks.answer_of("q1") == "first"
