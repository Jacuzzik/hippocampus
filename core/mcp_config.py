"""MCP servers per agent: add, remove and list the servers in one agent folder's .mcp.json.

The agent's command-line tool reads this file when it starts in its folder, so a server added here
is on for that agent only, which is the per-agent switch. The user's own ~/.claude.json is never
written. A server is a command with arguments (stdio) or an https address; no environment values
are taken here, so no key is ever written by the app, and the list masks anything that looks like
a secret. Other keys in the file are kept as they are.
"""

import json
import re
import shlex
from pathlib import Path
from typing import Any

from core import safe_write
from core.connectors import mask_args, mask_url

FILE = ".mcp.json"
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")
SERVERS_MAX = 40
LINE_MAX = 1000


def _read(folder: Path) -> dict[str, Any]:
    path = folder / FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(
            f"{FILE} in {folder.name} is not valid JSON, so it is left alone."
        ) from error
    if not isinstance(data, dict):
        raise ValueError(f"{FILE} in {folder.name} is not an object, so it is left alone.")
    return data


def servers(folder: Path) -> list[dict[str, str]]:
    found = _read(folder).get("mcpServers")
    rows = []
    for name, spec in (found if isinstance(found, dict) else {}).items():
        if not isinstance(spec, dict):
            continue
        if spec.get("url"):
            shown, kind = mask_url(str(spec["url"])), "http"
        else:
            shown = " ".join([str(spec.get("command", "")), *mask_args(spec.get("args") or [])])
            kind = "stdio"
        env = sorted(spec["env"]) if isinstance(spec.get("env"), dict) else []
        rows.append(
            {"name": str(name), "kind": kind, "command": shown.strip(), "env": ", ".join(env)}
        )
    return rows


def add(folder: Path, name: object, line: object) -> list[dict[str, str]]:
    """Add or replace one server. `line` is an https address or a command line."""
    if not folder.is_dir():
        raise ValueError("This agent has no working folder.")
    if not isinstance(name, str) or not NAME.match(name):
        raise ValueError("The name is letters, digits, - and _ only, up to 48.")
    if not isinstance(line, str) or not line.strip() or len(line) > LINE_MAX:
        raise ValueError("Write the command that starts the server, or its https address.")
    line = line.strip()
    if line.startswith(("http://", "https://")):
        if not line.startswith("https://"):
            raise ValueError("Only an https address is taken.")
        spec: dict[str, Any] = {"type": "http", "url": line}
    else:
        try:
            parts = shlex.split(line)
        except ValueError as error:
            raise ValueError(f"The command could not be read: {error}.") from error
        spec = {"command": parts[0], "args": parts[1:]}
    data = _read(folder)
    current = data.get("mcpServers") if isinstance(data.get("mcpServers"), dict) else {}
    if name not in current and len(current) >= SERVERS_MAX:
        raise ValueError(f"An agent can have at most {SERVERS_MAX} servers.")
    data["mcpServers"] = {**current, name: spec}
    safe_write.write_text(folder / FILE, json.dumps(data, indent=2) + "\n")
    return servers(folder)


def remove(folder: Path, name: object) -> list[dict[str, str]]:
    data = _read(folder)
    current = data.get("mcpServers") if isinstance(data.get("mcpServers"), dict) else {}
    if not isinstance(name, str) or name not in current:
        raise ValueError("No server has that name in this agent's folder.")
    data["mcpServers"] = {k: v for k, v in current.items() if k != name}
    safe_write.write_text(folder / FILE, json.dumps(data, indent=2) + "\n")
    return servers(folder)
