"""The assistant loop: ask the model, run the tools it asks for, repeat until it answers.

Every await checks the kill switch, so a stop ends the loop within the poll interval.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Collection
from typing import Any, TypeVar

from ai.providers.base import Reply, ToolCall, ToolSpec
from ai.router import Router
from tools.gate import AskQueue, ConfirmGate, KillSwitch, Stopped
from tools.registry import Tool, needs_confirm

logger = logging.getLogger("hippocampus.agent")

MAX_STEPS = 8
# The config default (config/settings.toml); the core always passes the configured value.
DEFAULT_MAX_TOOL_CALLS = 20
POLL_SECONDS = 0.05
MAX_RESULT_CHARS = 4000
ASK_TOOL = "ask_user"
ASK_SPEC = ToolSpec(
    ASK_TOOL,
    "Ask the user a question and wait for the reply, when a fact only the user holds blocks you.",
    {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
)
T = TypeVar("T")

Emit = Callable[[dict[str, Any]], None]


class AgentError(Exception):
    pass


class AgentPaused(Exception):
    """The request used its tool-call limit. `messages` lets the next request carry on from here."""

    def __init__(self, limit: int, messages: list[dict[str, Any]]) -> None:
        super().__init__(f"paused after {limit} tool calls")
        self.limit = limit
        self.messages = messages


class Agent:
    def __init__(
        self,
        router: Router,
        tools: dict[str, Tool],
        kill: KillSwitch,
        gate: ConfirmGate,
        emit: Emit,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
        allowed: Collection[str] | None = None,
        asks: AskQueue | None = None,
    ) -> None:
        self.router = router
        self.tools = tools
        self.kill = kill
        self.gate = gate
        self.emit = emit
        self.max_tool_calls = max_tool_calls
        self.allowed = None if allowed is None else frozenset(allowed)  # None: every tool
        self.asks = asks  # None: the assistant cannot ask the user
        self.tokens_used = 0  # provider tokens over every model reply in this request

    async def run(self, text: str, messages: list[dict[str, Any]] | None = None) -> str:
        """Answer `text`. Pass the messages of a paused request to carry on from them."""
        specs = [
            ToolSpec(t.name, t.description, t.parameters)
            for t in self.tools.values()
            if self._allowed(t.name)
        ]
        if self.asks is not None:
            specs.append(ASK_SPEC)
        messages = [] if messages is None else messages
        messages.append({"role": "user", "content": text})
        calls = 0
        for _ in range(MAX_STEPS):
            reply: Reply = await self._until_stopped(self.router.chat(messages, specs))
            self.tokens_used += reply.tokens
            messages.append(
                {"role": "assistant", "content": reply.text, "tool_calls": reply.tool_calls}
            )
            if not reply.tool_calls:
                return reply.text
            for call in reply.tool_calls:
                if calls >= self.max_tool_calls:
                    result = f"Not run: {self.max_tool_calls} tool calls were already used."
                else:
                    calls += 1
                    result = await self._run_tool(call)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result}
                )
            if calls >= self.max_tool_calls:
                raise AgentPaused(self.max_tool_calls, messages)
        raise AgentError(f"no answer within {MAX_STEPS} steps")

    def _allowed(self, name: str) -> bool:
        return self.allowed is None or name in self.allowed

    async def _run_tool(self, call: ToolCall) -> str:
        if call.name == ASK_TOOL and self.asks is not None:
            return await self._ask(self.asks, call)
        tool = self.tools.get(call.name)
        if tool is None:
            return f"error: there is no tool named {call.name}"
        if not self._allowed(tool.name):
            self._log(call, tool, "refused")
            return f"error: this assistant may not use {call.name}."
        self._log(call, tool, "requested")
        try:
            if needs_confirm(tool.tier):
                preview = tool.preview(call.args) if tool.preview else json.dumps(call.args)
                if not await self._confirm(call, tool, preview):
                    self._log(call, tool, "declined")
                    return "The user declined this change. Do not retry it."
            self._log(call, tool, "running")
            result = await self._until_stopped(asyncio.to_thread(tool.run, call.args))
        except Stopped:
            raise
        except Exception as exc:  # the model sees the error; the log keeps the trace
            logger.exception("Tool %s failed", tool.name)
            self._log(call, tool, "failed")
            return f"error: {exc}"
        self._log(call, tool, "done")
        return result[:MAX_RESULT_CHARS]

    async def _ask(self, asks: AskQueue, call: ToolCall) -> str:
        question = call.args.get("question")
        if not isinstance(question, str) or not question.strip():
            return "error: ask_user needs a non-empty question"
        asks.open(call.id, question.strip())
        self.emit({"event": "ask", "call": call.id, "question": question.strip()})
        try:
            while (answer := asks.answer_of(call.id)) is None:
                self.kill.check()
                await asyncio.sleep(POLL_SECONDS)
            return answer
        finally:
            asks.close(call.id)

    async def _confirm(self, call: ToolCall, tool: Tool, preview: str) -> bool:
        self.gate.open(call.id)
        self.emit(
            {
                "event": "confirm",
                "call": call.id,
                "name": tool.name,
                "tier": tool.tier,
                "preview": preview,
            }
        )
        try:
            while (decision := self.gate.decision(call.id)) is None:
                self.kill.check()
                await asyncio.sleep(POLL_SECONDS)
            return decision
        finally:
            self.gate.close(call.id)

    async def _until_stopped(self, work: Awaitable[T]) -> T:
        task = asyncio.ensure_future(work)
        try:
            self.kill.check()
            while True:
                done, _ = await asyncio.wait({task}, timeout=POLL_SECONDS)
                if done:
                    return task.result()
                self.kill.check()
        finally:
            if not task.done():
                task.cancel()

    def _log(self, call: ToolCall, tool: Tool, status: str) -> None:
        logger.info("tool %s (%s) %s", tool.name, tool.tier, status)
        self.emit(
            {
                "event": "tool",
                "call": call.id,
                "name": tool.name,
                "tier": tool.tier,
                "status": status,
            }
        )
