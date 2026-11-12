"""One Claude Code session per agent, kept on disk so it survives an app restart.

Each agent gets its session ID the first time it talks. Later calls resume that session.
A new session is made only when the user switches it, by removing the agent's entry.
"""

import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from core.settings import ROOT

FILE = ROOT / "data" / "storage" / "claude_sessions.json"
# Terminal and chat both read and rewrite this file; one lock keeps a concurrent write from dropping an agent's session.
_LOCK = threading.Lock()


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(agent: str, path: Path | None = None) -> dict[str, Any]:
    """The agent's entry: {"id": uuid, "started": bool}. Created with a new ID when missing."""
    path = FILE if path is None else path
    with _LOCK:
        data = _read(path)
        entry = data.get(agent)
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            entry = {"id": str(uuid.uuid4()), "started": False}
            data[agent] = entry
            _write(path, data)
        return entry


def mark_started(agent: str, path: Path | None = None) -> None:
    """Call after the session's first reply, so later calls resume it instead of creating it."""
    path = FILE if path is None else path
    with _LOCK:
        data = _read(path)
        if agent in data:
            data[agent]["started"] = True
            _write(path, data)


def set_engine_for(agent: str, engine: str, path: Path | None = None) -> None:
    """Record the provider and model the agent's session runs with. A different one drops the session: a new one starts."""
    path = FILE if path is None else path
    with _LOCK:
        data = _read(path)
        entry = data.get(agent)
        if isinstance(entry, dict) and entry.get("engine") not in (None, engine):
            data.pop(agent, None)
            entry = None
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            entry = {"id": str(uuid.uuid4()), "started": False}
        entry["engine"] = engine
        data[agent] = entry
        _write(path, data)


def has_transcript(session: str) -> bool:
    """True when Claude Code has written this session's transcript, so it can be resumed."""
    return next((Path.home() / ".claude" / "projects").glob(f"*/{session}.jsonl"), None) is not None


def switch(agent: str, path: Path | None = None) -> None:
    """Drop the agent's session: the next call starts a new one."""
    path = FILE if path is None else path
    with _LOCK:
        data = _read(path)
        data.pop(agent, None)
        _write(path, data)


TOKEN_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def folder_tokens(folder: str) -> int:
    """Tokens this month across the Claude Code sessions run in `folder`, each reply counted once."""
    from datetime import datetime

    base = Path.home() / ".claude" / "projects" / folder.replace("/", "-")
    start = datetime.now().astimezone().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    seen: set[str] = set()
    total = 0
    for path in base.glob("*.jsonl"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            message = row.get("message") or {}
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            when = row.get("timestamp")
            if when and datetime.fromisoformat(when.replace("Z", "+00:00")) < start:
                continue
            key = message.get("id") or row.get("uuid") or line
            if key in seen:
                continue
            seen.add(key)
            total += sum(int(usage.get(k) or 0) for k in TOKEN_KEYS)
    return total + codex_tokens(folder) + opencode_tokens(folder)


def folder_activity(folder: str) -> dict[str, Any]:
    """This month's Claude Code activity in `folder`: tool calls, the last tool used, and the last reply's time."""
    from datetime import datetime

    base = Path.home() / ".claude" / "projects" / folder.replace("/", "-")
    start = datetime.now().astimezone().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    seen: set[str] = set()
    calls, last_tool, last_reply = 0, None, None
    for path in base.glob("*.jsonl"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            message = row.get("message") or {}
            when = row.get("timestamp")
            if message.get("role") != "assistant" or not when:
                continue
            if datetime.fromisoformat(when.replace("Z", "+00:00")) < start:
                continue
            if last_reply is None or when > last_reply:
                last_reply = when
            for block in message.get("content") or []:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("id") not in seen
                ):
                    seen.add(block.get("id"))
                    calls += 1
                    last_tool = _tool_text(block.get("name"), block.get("input")) or last_tool
    if last_tool is None:
        last_tool = codex_last_tool(folder)
    return {"tool_calls": calls, "last_tool": last_tool, "last_reply": last_reply}


def _tool_text(name: str | None, inputs: object) -> str | None:
    """A tool call as "name: command or description", the same form the terminal shows."""
    if not name:
        return None
    inputs = inputs if isinstance(inputs, dict) else {}
    detail = inputs.get("command") or inputs.get("cmd") or inputs.get("description") or ""
    return f"{name}: {detail}" if detail else name


def codex_last_tool(folder: str) -> str | None:
    """The newest Codex CLI tool call run in `folder`, as "name: command"; None when there is none."""
    sessions = sorted(
        (Path.home() / ".codex" / "sessions").glob("*/*/*/rollout-*.jsonl"), reverse=True
    )
    for path in sessions[:200]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        cwd = None
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") == "session_meta":
                cwd = (row.get("payload") or {}).get("cwd")
                break
        if cwd != folder:
            continue
        for line in reversed(lines):
            try:
                payload = json.loads(line).get("payload") or {}
            except (ValueError, AttributeError):
                continue
            if payload.get("type") in ("function_call", "custom_tool_call"):
                args = payload.get("arguments")
                try:
                    inputs = json.loads(args) if isinstance(args, str) else args
                except ValueError:
                    inputs = {}
                if not isinstance(inputs, dict) or not inputs:
                    # Codex's exec tool carries its command inside a script string: cmd:"...".
                    script = payload.get("input") if isinstance(payload.get("input"), str) else ""
                    found = re.search(r'cmd:\s*"((?:[^"\\]|\\.)*)"', script)
                    inputs = {"command": found.group(1)} if found else {}
                # Codex's exec tool shows just the command, without the "exec:" label.
                if payload.get("name") == "exec" and inputs.get("command"):
                    return inputs["command"]
                return _tool_text(payload.get("name"), inputs)
        # This session has no tool call yet: keep looking in older sessions in the same folder.
    return None


def codex_tokens(folder: str) -> int:
    """Tokens this month across the Codex CLI sessions run in `folder`, from each session's running total."""
    from datetime import datetime

    start = datetime.now().astimezone().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = 0
    for path in (Path.home() / ".codex" / "sessions").glob("*/*/*/rollout-*.jsonl"):
        try:
            when = datetime.strptime(path.name[8:18], "%Y-%m-%d").astimezone()
        except ValueError:
            continue
        if when < start:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        cwd, last = None, 0
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            payload = row.get("payload") or {}
            if row.get("type") == "session_meta":
                cwd = payload.get("cwd")
            elif payload.get("type") == "token_count":
                info = (payload.get("info") or {}).get("total_token_usage") or {}
                last = int(info.get("total_tokens") or 0)
        if cwd == folder:
            total += last
    return total


def context_percent(agent: str, window: int = 200_000) -> int:
    """How full the agent's Claude Code context is, from its newest reply's token usage.

    shortcut: assumes a 200k window, upgrade: read the model's real window size
    """
    found = _transcript(agent)
    if found is None:
        return 0
    try:
        lines = found.read_text(encoding="utf-8").splitlines()[-300:]
    except OSError:
        return 0
    for line in reversed(lines):
        try:
            usage = json.loads(line).get("message", {}).get("usage")
        except (ValueError, AttributeError):
            continue
        if isinstance(usage, dict):
            used = sum(
                int(usage.get(key) or 0)
                for key in (
                    "input_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                )
            )
            return min(100, used * 100 // window)
    return 0


def _transcript(agent: str) -> Path | None:
    """The agent's Claude Code session file, or None before it has one."""
    session = get(agent)["id"]
    # Session IDs are unique, so find the file in whichever project folder the agent runs in.
    return next((Path.home() / ".claude" / "projects").glob(f"*/{session}.jsonl"), None)


def open_tool_calls(agent: str) -> list[str]:
    """Tool calls the agent started and has not finished: what its terminal is running now."""
    found = _transcript(agent)
    if found is None:
        return []
    try:
        lines = found.read_text(encoding="utf-8").splitlines()[-400:]
    except OSError:
        return []
    started: dict[str, str] = {}
    done: set[str] = set()
    for line in lines:
        try:
            content = json.loads(line).get("message", {}).get("content")
        except (ValueError, AttributeError):
            continue
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                inputs = block.get("input") or {}
                detail = inputs.get("command") or inputs.get("description") or ""
                started[str(block.get("id"))] = (
                    f"{block.get('name')}: {detail}" if detail else str(block.get("name"))
                )
            elif block.get("type") == "tool_result":
                done.add(str(block.get("tool_use_id")))
    return [name for call, name in started.items() if call not in done]


# Sessions an agent ran before its project folder moved. Read only: used for the card's last command when the
# current session has no tool calls yet. Session files are never changed.
PREVIOUS_SESSIONS: dict[str, str] = {"hippoherman": "2978bcce-b4de-4727-bd98-f0adc3a4c96f"}


def _newest_tool_call(found: Path) -> str | None:
    try:
        lines = found.read_text(encoding="utf-8").splitlines()[-400:]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            content = json.loads(line).get("message", {}).get("content")
        except (ValueError, AttributeError):
            continue
        for block in reversed(content if isinstance(content, list) else []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                inputs = block.get("input") or {}
                detail = inputs.get("command") or inputs.get("description") or ""
                return f"{block.get('name')}: {detail}" if detail else str(block.get("name"))
    return None


def tool_trace(agent: str, limit: int = 100) -> list[dict[str, Any]]:
    """The agent's recent tool calls, newest first: when, which tool, what it was asked, and whether it failed.

    Read from the agent's Claude Code session file. Other CLIs keep no file this can read, so they give no rows.
    """
    found = _transcript(agent)
    if found is None:
        return []
    try:
        lines = found.read_text(encoding="utf-8").splitlines()[-2000:]
    except OSError:
        return []
    calls: dict[str, dict[str, Any]] = {}
    for line in lines:
        try:
            row = json.loads(line)
            content = row.get("message", {}).get("content")
        except (ValueError, AttributeError):
            continue
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                inputs = block.get("input") if isinstance(block.get("input"), dict) else {}
                detail = (
                    inputs.get("command")
                    or inputs.get("description")
                    or inputs.get("file_path")
                    or inputs.get("path")
                    or inputs.get("query")
                    or ""
                )
                calls[str(block.get("id"))] = {
                    "at": row.get("timestamp"),
                    "tool": str(block.get("name")),
                    "detail": str(detail)[:300],
                    "status": "running",
                }
            elif block.get("type") == "tool_result" and str(block.get("tool_use_id")) in calls:
                calls[str(block.get("tool_use_id"))]["status"] = (
                    "failed" if block.get("is_error") else "done"
                )
    return list(calls.values())[::-1][:limit]


def last_tool_call(agent: str) -> str | None:
    """The newest tool call the agent made, finished or not, as "name: detail"; None before any."""
    found = _transcript(agent)
    newest = _newest_tool_call(found) if found is not None else None
    if newest is None and agent in PREVIOUS_SESSIONS:
        previous = next(
            (Path.home() / ".claude" / "projects").glob(f"*/{PREVIOUS_SESSIONS[agent]}.jsonl"), None
        )
        newest = _newest_tool_call(previous) if previous is not None else None
    return newest


def last_model(agent: str) -> str | None:
    """The model the agent's Claude Code session last answered with; None before any answer."""
    found = _transcript(agent)
    if found is None:
        return None
    try:
        lines = found.read_text(encoding="utf-8").splitlines()[-400:]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            model = json.loads(line).get("message", {}).get("model")
        except (ValueError, AttributeError):
            continue
        if isinstance(model, str) and model and not model.startswith("<"):
            return model
    return None


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # A unique temp name, so two writers never share one file.
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


OPENCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def _opencode(query: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    """Rows from OpenCode's database, read-only; none when the database is missing or unreadable."""
    import sqlite3

    if not OPENCODE_DB.is_file():
        return []
    try:
        with sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True) as db:
            return db.execute(query, params).fetchall()
    except sqlite3.Error:
        return []


def opencode_last_tool(folder: str) -> str | None:
    """The newest OpenCode tool call run in `folder`, as "name: command"; None when there is none."""
    rows = _opencode(
        "select p.data from part p join session s on s.id = p.session_id "
        "where s.directory = ? and json_extract(p.data, '$.type') = 'tool' order by p.time_created desc limit 1",
        (folder,),
    )
    if not rows:
        return None
    try:
        part = json.loads(rows[0][0])
    except (ValueError, TypeError):
        return None
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    inputs = dict(state.get("input")) if isinstance(state.get("input"), dict) else {}
    # File tools name their target differently; show it where the other tools show a command.
    if not inputs.get("command"):
        inputs["command"] = (
            inputs.get("filePath") or inputs.get("path") or inputs.get("pattern") or ""
        )
    return _tool_text(part.get("tool"), inputs)


def opencode_tokens(folder: str) -> int:
    """Tokens this month across the OpenCode sessions run in `folder`, from each assistant reply's count."""
    from datetime import datetime

    start = datetime.now().astimezone().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = _opencode(
        "select m.data from message m join session s on s.id = m.session_id "
        "where s.directory = ? and m.time_created >= ?",
        (folder, int(start.timestamp() * 1000)),
    )
    total = 0
    for (data,) in rows:
        try:
            tokens = json.loads(data).get("tokens") or {}
        except (ValueError, TypeError, AttributeError):
            continue
        total += int(tokens.get("total") or 0)
    return total
