"""The assistant loop: ask the model, run the tools it asks for, repeat until it answers.

Every await checks the kill switch, so a stop ends the loop within the poll interval.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from ai.providers.base import Reply, ToolCall, ToolSpec
from ai.router import Router
from tools.gate import ConfirmGate, KillSwitch, Stopped
from tools.registry import Tool, needs_confirm

logger = logging.getLogger("hippocampus.agent")

MAX_STEPS = 8
POLL_SECONDS = 0.05
MAX_RESULT_CHARS = 4000
T = TypeVar("T")

Emit = Callable[[dict[str, Any]], None]


class AgentError(Exception):
    pass


class Agent:
    def __init__(
        self,
        router: Router,
        tools: dict[str, Tool],
        kill: KillSwitch,
        gate: ConfirmGate,
        emit: Emit,
    ) -> None:
        self.router = router
        self.tools = tools
        self.kill = kill
        self.gate = gate
        self.emit = emit

    async def run(self, text: str) -> str:
        specs = [ToolSpec(t.name, t.description, t.parameters) for t in self.tools.values()]
        messages: list[dict[str, Any]] = [{"role": "user", "content": text}]
        for _ in range(MAX_STEPS):
            reply: Reply = await self._until_stopped(self.router.chat(messages, specs))
            messages.append(
                {"role": "assistant", "content": reply.text, "tool_calls": reply.tool_calls}
            )
            if not reply.tool_calls:
                return reply.text
            for call in reply.tool_calls:
                result = await self._run_tool(call)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result}
                )
        raise AgentError(f"no answer within {MAX_STEPS} steps")

    async def _run_tool(self, call: ToolCall) -> str:
        tool = self.tools.get(call.name)
        if tool is None:
            return f"error: there is no tool named {call.name}"
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
