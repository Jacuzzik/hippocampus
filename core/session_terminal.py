"""The terminal calls from the window: start, input, resize, stop and the rest, passed on to core/terminal.py."""

from datetime import datetime
from typing import Any

from core import (
    added_agents,
    briefing,
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
                text = briefing.main_briefing(self.settings.vault)
            else:
                text = briefing.agent_briefing(
                    agent, saved, folder, self.settings.vault, self.hive_path / agent / "outbox"
                )
            vault = str(self.settings.vault) if self.settings.vault else None
            block_tools = bool(request.get("block_tools", False))
            # The start-up inbox is written each time a terminal starts, so a new agent gets it as soon as its terminal opens.
            agents = added_agents.load(self.agents_path)
            inbox_path = startup_inbox.write(self.hive_path, agent, agents)
            shell = self.settings.agent_shell
            # The real rules for this start, computed from the switches, so the briefing cannot disagree with them.
            sandboxed = shell and sandbox_for(provider)
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
                agent, provider, rows, cols, model, folder, text, vault, block_tools, shell
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
