"""Claude through the Claude Code CLI, logged in with the user's own account. No API key is used.

Text only: the CLI call returns the reply, so the assistant's tools are not offered on this path.
shortcut: no tool calls via the CLI, add a tool bridge later if the assistant needs tools with Claude Code.
"""

import asyncio
import json
import shutil
from typing import Any

from ai import cli_sessions, network
from ai.providers.base import NetworkBlocked, ProviderError, Reply, ToolSpec

CLI = "claude"


def cli_ready() -> bool:
    """True when the Claude Code CLI is on the PATH. Login is checked by the CLI itself on each call."""
    return shutil.which(CLI) is not None


def _newest(messages: list[dict[str, Any]]) -> str:
    # The Claude Code session keeps the history, so only the newest user message is sent.
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


class ClaudeCliProvider:
    name = "claude-cli"

    def __init__(self, model: str, agent: str = "hippo", timeout: float = 120.0) -> None:
        self.model = model
        self.agent = agent
        self.timeout = timeout

    async def chat(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Reply:
        if not network.allows_model_calls():
            raise NetworkBlocked(f"network is {network.mode().capitalize()}: no call to the Claude CLI")
        binary = shutil.which(CLI)
        if binary is None:
            raise ProviderError("the Claude Code CLI is not installed")
        session = cli_sessions.get(self.agent)
        # The first call creates the agent's session; later calls resume it, across app restarts.
        resume = ["--resume", session["id"]] if session["started"] else ["--session-id", session["id"]]
        args = [binary, "-p", _newest(messages), "--output-format", "json", *resume]
        if self.model:
            args += ["--model", self.model]
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                # stdin must not be the sidecar's pipe: claude -p would read the app's messages and hang.
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except TimeoutError as exc:
            raise ProviderError("the Claude Code CLI did not answer in time") from exc
        except OSError as exc:
            raise ProviderError(f"could not start the Claude Code CLI: {exc}") from exc
        if proc.returncode != 0:
            # The CLI's own message says if the login is missing; show a short part only.
            detail = (err or out).decode("utf-8", "replace").strip()[:200]
            raise ProviderError(f"the Claude Code CLI failed (exit {proc.returncode}): {detail or 'no message'}")
        try:
            data = json.loads(out.decode("utf-8", "replace"))
        except ValueError as exc:
            raise ProviderError("the Claude Code CLI gave an unreadable reply") from exc
        if data.get("is_error"):
            raise ProviderError(str(data.get("result") or "the Claude Code CLI reported an error")[:200])
        usage = data.get("usage") or {}
        tokens = int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
        cli_sessions.mark_started(self.agent)
        return Reply(text=str(data.get("result") or ""), tokens=tokens)
