"""The terminal calls from the window: start, input, resize, stop and the rest, passed on to core/terminal.py."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from ai import cli_sessions
from core import (
    added_agents,
    autonomy,
    briefing,
    note_actions,
    pins,
    sandbox,
    startup_inbox,
)
from core.settings import (
    ROOT,
)
from core.terminal import OPENCODE_FOR, sandbox_for


class TerminalPart:
    def terminal(self, method: str, request: dict[str, Any]) -> dict[str, Any]:
        """The agent's live terminal: start its CLI, send it keys, resize it, stop it."""
        agent = request.get("agent")
        if not isinstance(agent, str) or not agent:
            raise ValueError(f'"{method}" needs an "agent" id')
        rows, cols = int(request.get("rows") or 24), int(request.get("cols") or 80)
        if method == "terminal_start":
            provider = str(request.get("provider") or "")
            model = str(request.get("model") or "")
            if provider == "ollama" and not model:
                model = self.settings.ollama_model
            elif provider in OPENCODE_FOR and not model:
                # An API provider runs the model saved in the engine switch.
                model = self.settings.provider_model
            elif provider == "claude" and not model:
                # Claude runs the model saved in the engine switch, so a model change reaches its CLI.
                model = self.settings.claude_model
            folder = request.get("folder") if isinstance(request.get("folder"), str) else None
            if folder is None and self.settings.vault:
                folder = str(self.settings.vault)
            saved = next(
                (a for a in added_agents.load(self.agents_path) if a.get("id") == agent), {}
            )
            # The wording lives in core/briefing.py; the parts that differ per agent are filled in there.
            if agent == "hippoherman":
                outbox = self.hive_path / agent / "outbox"
                outbox.mkdir(parents=True, exist_ok=True)  # the lead routes work through it
                text = briefing.main_briefing(self.settings.vault, outbox)
            else:
                text = briefing.agent_briefing(
                    agent, saved, folder, self.settings.vault, self.hive_path / agent / "outbox"
                )
            reader = self._pin_reader()
            pinned_text = pins.section(pins.gather(pins.paths(saved), reader))
            if pinned_text:
                text = briefing.add_section(text, "Pinned notes", pinned_text)
            handoff_text = pins.handoff(agent, reader) if agent != "hippoherman" else ""
            if handoff_text:
                text = briefing.add_section(text, "Handoff from your last session", handoff_text)
            vault = str(self.settings.vault) if self.settings.vault else None
            block_tools = bool(request.get("block_tools", False))
            # The start-up inbox is written each time a terminal starts, so a new agent gets it as soon as its terminal opens.
            agents = added_agents.load(self.agents_path)
            inbox_path = startup_inbox.write(self.hive_path, agent, agents)
            shell = self.settings.agent_shell
            # The real rules for this start, computed from the switches, so the briefing cannot disagree with them.
            # A custom command always runs in the sandbox (core/terminal.py refuses it where there is none).
            sandboxed = provider == "custom" or (shell and sandbox_for(provider))
            limits = sandbox.policy_lines(
                shell=agent == "hippoherman" or sandboxed,
                sandboxed=sandboxed,
                blocked=block_tools,
                app_root=ROOT,
            )
            text, mark = briefing.finish(text, inbox_path, limits)
            problems = briefing.lint(text)
            if problems:
                # Stops before the agent starts: an agent with a broken briefing would run without its rules.
                raise ValueError("This agent cannot start. " + " ".join(problems))
            self.briefing_stamps[agent] = {
                **mark,
                "at": datetime.now().isoformat(timespec="seconds"),
            }
            started = self.terminals.start(
                agent,
                provider,
                rows,
                cols,
                model,
                folder,
                text,
                vault,
                block_tools,
                shell,
                # The custom command and the autonomy level come from the saved agent, never from the window.
                command=str(saved.get("command") or "") if provider == "custom" else "",
                autonomy_level=saved.get("autonomy", autonomy.DEFAULT) if saved else None,
            )
            # The start-up inbox is sent into the terminal chat by the delivery loop, once the terminal has settled.
            # Only a CLI that has just started gets it: reopening the window reattaches to a running CLI, and
            # typing the inbox in again each time spent the agent's tokens on a message it had already read.
            if not started.get("reattached"):
                self.inbox_pending[agent] = str(inbox_path)
            return started
        if method == "terminal_input":
            self.terminals.write(agent, str(request.get("data") or ""))
        elif method == "terminal_resize":
            self.terminals.resize(agent, rows, cols)
        else:
            self.terminals.stop(agent)
        return {"ok": True}

    def remote_status(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.terminals.remote_status(request["agent"])

    def terminal_context(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"percent": cli_sessions.context_percent(request["agent"])}

    def _pin_reader(self) -> Callable[[str], str] | None:
        """Reads a whole note by its path, or None when no vault is open."""
        if self.indexer is None:
            return None
        return lambda path: note_actions.read_full(self.indexer, self.lock, path)

    def agent_pins(self, request: dict[str, Any]) -> dict[str, Any]:
        """The notes pinned to an agent, each with its token estimate, and a warning past the limit."""
        agent = request.get("agent")
        if not isinstance(agent, str) or not agent:
            raise ValueError('"agent_pins" needs an "agent" id')
        saved = next((a for a in added_agents.load(self.agents_path) if a.get("id") == agent), {})
        return pins.summary(pins.gather(pins.paths(saved), self._pin_reader()))

    def briefing_preview(self, request: dict[str, Any]) -> dict[str, Any]:
        """The briefing a new agent would start with, from the words typed so far. Nothing is saved or started.
        The two sections added at start (the start-up inbox and the limits in force) are not in the preview."""

        def words(key: str, limit: int) -> str:
            value = request.get(key)
            return value.strip()[:limit] if isinstance(value, str) else ""

        name = words("name", 80) or "New agent"
        saved = {
            "name": name,
            "description": words("description", 100),
            "goal": words("goal", 4000),
        }
        folder = words("folder", 400) or None
        text = briefing.agent_briefing(
            "new-agent", saved, folder, self.settings.vault, self.hive_path / "new-agent" / "outbox"
        )
        return {"text": text, "version": briefing.VERSION, "characters": len(text)}

    def terminal_rebrief(self, request: dict[str, Any]) -> dict[str, Any]:
        """Points a running agent at its briefing again. The briefing file itself is not rewritten."""
        who = request["agent"]
        path = self.terminals.resend_briefing(who)
        self.note("handoff", text=f"briefing sent again to {who}")
        return {"path": path}

    def terminal_traces(self, request: dict[str, Any]) -> dict[str, Any]:
        """What the agent ran, newest first: every tool call with its time and outcome, shell commands included.
        `limit` (1 to 500, default 100) is how many; the replay view asks for more."""
        limit = request.get("limit", 100)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            limit = 100
        return {"traces": cli_sessions.tool_trace(request["agent"], limit)}

    def terminal_command(self, request: dict[str, Any]) -> dict[str, Any]:
        # "boot" changes each time the backend starts, so the window can tell a restart from a quiet moment
        # and start the agents' programs again (they stop with the backend).
        who = str(request.get("agent") or "")
        return {
            **self.terminals.info(who),
            "boot": self.boot,
            "briefing": self.briefing_stamps.get(who),
        }
