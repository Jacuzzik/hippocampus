"""Everything the app can connect to, as one list of rows the Settings > Connectors page draws.

A row says what the connector is, its state and why. A state is "Connected" only when a real check
succeeded in this call (an answer from Ollama, a login in `gh`, a list read); a connector that cannot
run yet is a row in state "Needs setup" with the reason. Nothing here writes a token anywhere, and the
MCP list shows names and commands with every secret-looking value masked.
"""

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

STATES = ("Not connected", "Connected", "Needs setup", "Error")
OLLAMA_SECONDS = 3.0
GITHUB_SECONDS = 10.0
Row = dict[str, Any]


def row(
    ident: str,
    name: str,
    what: str,
    state: str,
    reason: str,
    needs: str = "",
    details: Iterable[str] = (),
    kind: str = "check",
) -> Row:
    if state not in STATES:
        raise ValueError(f"state must be one of {STATES}")
    return {
        "id": ident,
        "kind": kind,
        "name": name,
        "what": what,
        "state": state,
        "reason": reason,
        "needs": needs,
        "details": list(details),
        "checked": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


# --- Ollama -----------------------------------------------------------------------------------


def ollama(host: str, model: str, timeout: float = OLLAMA_SECONDS) -> Row:
    """Asks the Ollama server for its models (`GET <host>/api/tags`), with a time limit."""
    name, what = (
        "Local model (Ollama)",
        "Runs a model on this computer, with no key and no network.",
    )
    if urlsplit(host).scheme not in ("http", "https"):
        return row(
            "ollama", name, what, "Error", f"The host {host!r} must start with http:// or https://."
        )
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=timeout) as answer:
            models = [m["name"] for m in json.load(answer).get("models", []) if "name" in m]
    except (OSError, ValueError, KeyError) as exc:
        reason = f"Nothing answered at {host} within {timeout:g} seconds ({type(exc).__name__}). Start it with `ollama serve`."
        return row("ollama", name, what, "Not connected", reason, needs="Ollama running")
    if model and model not in models:
        reason = (
            f"Running at {host}, but the model {model} is not installed. Run `ollama pull {model}`."
        )
        return row("ollama", name, what, "Needs setup", reason, "The chosen model", models)
    return row(
        "ollama",
        name,
        what,
        "Connected",
        f"Answered at {host}. Model in use: {model}.",
        details=models,
    )


# --- GitHub (the user's own gh login) -------------------------------------------------------------


def github(
    timeout: float = GITHUB_SECONDS,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> Row:
    """Runs `gh auth status`. The app stores no GitHub token: it only asks gh whether you are logged in."""
    name, what = "GitHub", "Open issues for an agent's folder, shown on the Monitor tab."
    binary = which("gh")
    if binary is None:
        return row(
            "github", name, what, "Needs setup", "The gh tool is not installed.", "gh, logged in"
        )
    try:
        done = run([binary, "auth", "status"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return row("github", name, what, "Error", f"gh did not answer within {timeout:g} seconds.")
    except OSError as exc:
        return row("github", name, what, "Error", f"gh could not start: {exc}")
    text = f"{done.stdout}\n{done.stderr}"
    if done.returncode != 0:
        return row(
            "github",
            name,
            what,
            "Not connected",
            "You are not logged in. Run `gh auth login`.",
            "gh login",
        )
    found = re.search(r"Logged in to (\S+) (?:account|as) (\S+)", text)
    who = f"Logged in to {found.group(1)} as {found.group(2)}." if found else "Logged in."
    return row("github", name, what, "Connected", who)


# --- MCP servers, read from each command-line tool's own config ---------------------------------------

SECRET_WORDS = re.compile(r"(key|token|secret|passw|auth|bearer|credential)", re.IGNORECASE)
LONG_OPAQUE = re.compile(r"[A-Za-z0-9_\-+/=]{24,}")


def mask_args(args: list[Any]) -> list[str]:
    """Command arguments with anything that looks like a secret replaced by ***."""
    out: list[str] = []
    hide_next = False
    for raw in args:
        arg = str(raw)
        if hide_next:
            out.append("***")
            hide_next = False
        elif "=" in arg and SECRET_WORDS.search(arg.split("=", 1)[0]):
            out.append(f"{arg.split('=', 1)[0]}=***")
        elif arg.startswith("-") and SECRET_WORDS.search(arg):
            out.append(arg)
            hide_next = "=" not in arg
        elif "://" in arg:
            out.append(mask_url(arg))
        elif LONG_OPAQUE.fullmatch(arg) and "/" not in arg[:3]:
            out.append("***")
        else:
            out.append(arg)
    return out


def mask_url(url: str) -> str:
    """A web address without a login, password or query string."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}{parts.path}"


def _servers(file: Path, scope: str, nested: str | None = None) -> list[str]:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        return [f"Could not read {file.name}: {type(exc).__name__}"]
    blocks: list[tuple[str, dict[str, Any]]] = []
    if isinstance(data.get("mcpServers"), dict):
        blocks.append((scope, data["mcpServers"]))
    if nested and isinstance(data.get(nested), dict):
        for folder, project in data[nested].items():
            if isinstance(project, dict) and isinstance(project.get("mcpServers"), dict):
                blocks.append((f"project {Path(folder).name}", project["mcpServers"]))
    lines = []
    for where, servers in blocks:
        for name, spec in servers.items():
            if not isinstance(spec, dict):
                continue
            if spec.get("url"):
                command = mask_url(str(spec["url"]))
            else:
                command = " ".join(
                    [str(spec.get("command", "")), *mask_args(spec.get("args") or [])]
                )
            env = sorted(spec.get("env") or {}) if isinstance(spec.get("env"), dict) else []
            extra = f" (env: {', '.join(env)})" if env else ""
            lines.append(f"{name}: {command.strip()}{extra} [{where}]")
    return lines


def mcp(home: Path, folders: list[Path]) -> Row:
    """Lists the MCP servers in `~/.claude.json` and each folder's `.mcp.json`. Read only."""
    name = "MCP servers"
    what = "Extra tools for agents, read from each command-line tool's own config. The app only lists them."
    lines = _servers(home / ".claude.json", "user", nested="projects")
    for folder in dict.fromkeys(folders):
        lines += _servers(folder / ".mcp.json", f"project {folder.name}")
    problems = [line for line in lines if line.startswith("Could not read")]
    if problems:
        return row("mcp", name, what, "Error", problems[0], details=lines)
    if not lines:
        return row(
            "mcp",
            name,
            what,
            "Not connected",
            "No MCP servers in your CLI config files.",
            details=[],
        )
    reason = f"{len(lines)} server{'s' if len(lines) != 1 else ''} listed. Each command-line tool starts its own; secrets are masked."
    return row("mcp", name, what, "Not connected", reason, details=lines)


# --- Local things and cards that cannot run yet ----------------------------------------------------------


def webhooks(saved: int) -> Row:
    reason = (
        f"{saved} saved. Nothing listens on a network port, so no outside service can call them."
    )
    return row(
        "webhooks",
        "Webhooks",
        "A saved trigger that runs one local job after you approve it.",
        "Not connected" if saved == 0 else "Needs setup",
        reason,
        "A public address and a signing secret",
    )


def jobs(saved: int, enabled: int) -> Row:
    what = "Notes jobs that run on a timer, such as the weekly link check."
    return row("jobs", "Scheduled jobs", what, "Connected", f"{saved} set, {enabled} on.")


def planned() -> list[Row]:
    token = "A browser sign-in and a token in the OS keychain"
    rows = [
        row(
            "slack",
            "Slack",
            "One bot that answers in chosen channels and replies in threads.",
            "Needs setup",
            "No Slack calls are built yet.",
            "A token store and a message bridge in the backend",
        ),
        row(
            "responders",
            "Default responders",
            "Who answers Slack, and who takes a webhook's message.",
            "Needs setup",
            "Waits for the Slack and webhook connectors.",
            "Slack or a webhook connector",
        ),
        row(
            "notion",
            "Notion",
            "Read pages and databases into notes.",
            "Needs setup",
            "No Notion calls are built yet.",
            token,
        ),
        row(
            "calendar",
            "Google Calendar",
            "Show today's events in the daily brief.",
            "Needs setup",
            "No Calendar calls are built yet.",
            token,
        ),
        row(
            "gmail",
            "Gmail",
            "Read-only search of your mail for an agent.",
            "Needs setup",
            "No Gmail calls are built yet.",
            token,
        ),
        row(
            "drive",
            "Google Drive",
            "Read documents into the vault.",
            "Needs setup",
            "No Drive calls are built yet.",
            token,
        ),
        row(
            "access",
            "Agent access",
            "Which agent may use which connector. New agents get none by default.",
            "Needs setup",
            "Waits for a connector that an agent could use.",
            "At least one connected service",
        ),
        row(
            "plugins",
            "Plugins",
            "Bundles of skills and tools that install in one step.",
            "Needs setup",
            "No plugin format is defined yet.",
            "A plugin format",
        ),
    ]
    return [{**one, "kind": "card"} for one in rows]
