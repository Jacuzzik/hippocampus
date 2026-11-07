"""Chat tools for the main agent: see the agent list and send a task to an agent's inbox."""

from pathlib import Path
from typing import Any

from core import added_agents, inbox
from tools.registry import Tool


def agent_tools(hive: Path, agents_file: Path) -> dict[str, Tool]:
    def list_agents(args: dict[str, Any]) -> str:
        agents = added_agents.load(agents_file)
        if not agents:
            return "No agents have been added yet."
        return "\n".join(
            f"{a.get('name')} (id {a.get('id')}): job {a.get('description') or 'not set'}; goal {a.get('goal') or 'not set'}"
            for a in agents
        )

    def send_task(args: dict[str, Any]) -> str:
        to = str(args.get("to", "")).strip()
        known = {a.get("id") for a in added_agents.load(agents_file)}
        if to not in known:
            raise ValueError(f'No agent with id "{to}". Use list_agents to see the ids.')
        message_id = inbox.send(hive, "hippoherman", to, str(args.get("subject", "")), str(args.get("body", "")))
        return f"sent to {to} (message {message_id})"

    def send_preview(args: dict[str, Any]) -> str:
        return f'Send to {args.get("to")}: {args.get("subject", "")}\n{args.get("body", "")}'

    tools = [
        Tool(
            name="list_agents",
            tier="read",
            description="List the agents in the app, with each one's job and goal.",
            parameters={"type": "object", "properties": {}},
            run=list_agents,
        ),
        Tool(
            name="send_task",
            tier="act",
            description="Send a task to an agent's inbox. The agent reads it in its terminal. Asks the user first.",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "The agent id, from list_agents."},
                    "subject": {"type": "string"},
                    "body": {"type": "string", "description": "What the agent should do."},
                },
                "required": ["to", "subject", "body"],
            },
            run=send_task,
            preview=send_preview,
        ),
    ]
    return {tool.name: tool for tool in tools}
