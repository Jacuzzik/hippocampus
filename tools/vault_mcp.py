"""The vault tools for the Claude Code chat, served over MCP on stdio: `python -m tools.vault_mcp <vault>`.

The chat's Claude Code session can only use these tools, so it can search, read, create, edit and delete notes
through the same checks as the app (hub notes stay protected) and has no shell.
"""

import json
import sys
import threading
from pathlib import Path
from typing import Any

from core.settings import ROOT
from core.vault import open_index
from tools.vault_tools import vault_tools

PROTOCOL = "2024-11-05"
# The vault tools the Claude Code sessions may call; the names match tools/vault_tools.py.
VAULT_TOOLS = (
    "search_notes",
    "read_note",
    "create_note",
    "edit_note",
    "delete_note",
    "list_folders",
    "move_note",
    "export_note",
    "set_note_status",
)


def mcp_config(vault: str) -> str:
    """The Claude Code --mcp-config value that starts this server for a vault."""
    server = {
        "command": sys.executable,
        "args": ["-m", "tools.vault_mcp", vault],
        "env": {"PYTHONPATH": str(ROOT)},
    }
    return json.dumps({"mcpServers": {"vault": server}})


def _ok(mid: int | str | None, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _text(mid: int | str | None, text: str, error: bool = False) -> dict[str, Any]:
    return _ok(mid, {"content": [{"type": "text", "text": text}], "isError": error})


def handle(msg: dict[str, Any], tools: dict[str, Any]) -> dict[str, Any] | None:
    mid = msg.get("id")
    if mid is None:  # a notification: nothing to answer
        return None
    method = msg.get("method")
    if method == "initialize":
        return _ok(
            mid,
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "vault", "version": "1"},
            },
        )
    if method == "tools/list":
        listed = [
            {"name": t.name, "description": t.description, "inputSchema": t.parameters}
            for t in tools.values()
        ]
        return _ok(mid, {"tools": listed})
    if method == "tools/call":
        params = msg.get("params") or {}
        tool = tools.get(params.get("name"))
        if tool is None:
            return _text(mid, f"unknown tool: {params.get('name')}", error=True)
        try:
            return _text(mid, tool.run(params.get("arguments") or {}))
        except Exception as cause:  # the model sees the reason, the server keeps running
            return _text(mid, str(cause), error=True)
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "error": {"code": -32601, "message": f"unknown method: {method}"},
    }


def main() -> None:
    vault = Path(sys.argv[1]).resolve()
    indexer = open_index(vault, ROOT / "data" / "storage")
    tools = vault_tools(indexer, threading.RLock())
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = handle(msg, tools)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
