"""Claude through the Claude Code CLI, logged in with the user's own account. No API key is used.

Text only: the CLI call returns the reply, so the assistant's tools are not offered on this path.
shortcut: no tool calls via the CLI, add a tool bridge later if the assistant needs tools with Claude Code.
"""

import asyncio
import json
import os
import shutil
from typing import Any

from ai import cli_sessions, network
from tools.vault_mcp import VAULT_TOOLS, mcp_config
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

    def __init__(self, model: str, agent: str = "hippo", timeout: float = 120.0, vault: str | None = None) -> None:
        self.model = model
        self.agent = agent
        self.timeout = timeout
        self.vault = vault

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
        if self.vault:
            # The main chat answers from the vault notes, not the web: it can read the vault, and web search is off.
            # The notes are reached only through the app's vault tools (tools/vault_mcp.py): no shell, no web.
            args += [
                "--mcp-config",
                mcp_config(self.vault),
                "--strict-mcp-config",
                "--allowedTools",
                *[f"mcp__vault__{name}" for name in VAULT_TOOLS],
                # No built-in tools (no shell, no file browsing, no web): only the vault server's tools.
                "--tools",
                "",
                "--append-system-prompt",
                f"You are Hippoherman, the main agent (Boss) of the Hippocampus app. Questions about our plans, past decisions, "
                f"projects or the user: use search_notes and read_note on the vault, starting with MAIN, then Projects, Summaries "
                "and the other group notes, and answer from them only. The vault is the memory: do not answer from earlier chat history "
                "or the session transcript. If the notes do not say, say so. You have no shell and no web. "
                "Only touch notes; never scan hidden folders (names starting with a dot). When the user asks you to organise folders, "
                "call list_folders to see them, then move_note for each note the user agrees to move, and say what you moved. "
                "Keep answers short: do not list the files or folders you searched. "
                "To save something the user names a note for, find that note with search_notes and change it with edit_note; "
                "do not create a new note unless the user asks for one, and ask which note if it is unclear. "
                "A new note goes under its group: add a [[link]] to it in the matching group hub (Projects, Summaries, Agent Lists, "
                "Contacts, Socials or About User) so it is organized and takes that group's colour. If no group fits, ask. "
                "To delete a note the user asks you to delete, call delete_note; if it is protected, say so.",
            ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                # stdin must not be the sidecar's pipe: claude -p would read the app's messages and hang.
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # CLAUDE_CODE_CHILD_SESSION turns off transcript saving, so the chat's session could not be resumed.
                env={k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_CHILD_SESSION"},
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
