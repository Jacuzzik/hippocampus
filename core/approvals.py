"""N.12: approvals for an agent at the "Ask first" level, with the exact command or file change.

A Claude Code PreToolUse hook (core/approval_hook.py) writes one request file per tool call and waits. The app
lists the requests, shows the command or the diff, and writes the answer: approve once, approve for this folder, or
deny. Everything is plain files under the storage folder; nothing listens on a port.

  approvals/pending/<id>.json   a request waiting for an answer
  approvals/answers/<id>.json   {"decision": "once" | "folder" | "deny"}
  approvals/rules.json          folder rules the user approved
"""

import difflib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from core import safe_write

TOOLS = ("Bash", "Edit", "Write", "MultiEdit", "NotebookEdit")
DECISIONS = ("once", "folder", "deny")
WAIT_SECONDS = 600
DIFF_MAX = 20_000
COMMAND_MAX = 4_000


def _dirs(base: Path) -> tuple[Path, Path]:
    pending, answers = base / "pending", base / "answers"
    pending.mkdir(parents=True, exist_ok=True)
    answers.mkdir(parents=True, exist_ok=True)
    return pending, answers


def _under(path: str, folder: str) -> bool:
    try:
        return Path(path).resolve().is_relative_to(Path(folder).resolve())
    except (OSError, ValueError):
        return False


def _new_text(tool: str, spec: dict[str, Any], old: str) -> str:
    if tool == "Write":
        return str(spec.get("content", ""))
    if tool == "Edit":
        before, after = str(spec.get("old_string", "")), str(spec.get("new_string", ""))
        if not before:
            return old + after
        return (
            old.replace(before, after) if spec.get("replace_all") else old.replace(before, after, 1)
        )
    if tool == "MultiEdit":
        text = old
        for edit in spec.get("edits") or []:
            if isinstance(edit, dict):
                text = text.replace(
                    str(edit.get("old_string", "")), str(edit.get("new_string", "")), 1
                )
        return text
    return old


def describe(tool: str, spec: dict[str, Any]) -> dict[str, str]:
    """What the request shows: the exact command, or the unified diff of the file it would change."""
    if tool == "Bash":
        return {"command": str(spec.get("command", ""))[:COMMAND_MAX], "file": "", "diff": ""}
    name = str(spec.get("file_path") or spec.get("notebook_path") or "")
    try:
        old = Path(name).read_text(encoding="utf-8") if name and Path(name).is_file() else ""
    except (OSError, UnicodeDecodeError):
        old = ""
    new = _new_text(tool, spec, old)
    diff = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{Path(name).name}" if old else "/dev/null",
            tofile=f"b/{Path(name).name}",
        )
    )
    return {"command": "", "file": name, "diff": diff[:DIFF_MAX] or "(no visible change)"}


def rule_label(rule: dict[str, str]) -> str:
    if rule["tool"] == "Bash":
        word = rule.get("prefix") or "any command"
        return f"Run {word} commands in {rule['folder']}"
    return f"{rule['tool']} files in {rule['folder']}"


def rule_for(request: dict[str, Any]) -> dict[str, str]:
    """The rule "approve for this folder" would add for a request: this tool, in the folder the agent works in.
    A shell command is limited to the same first word, so approving `npm test` does not approve `rm`."""
    tool = str(request.get("tool", ""))
    rule = {"tool": tool, "folder": str(request.get("cwd", ""))}
    if tool == "Bash":
        words = str(request.get("command", "")).split()
        rule["prefix"] = words[0] if words else ""
    return rule


def matches(rule: dict[str, str], tool: str, cwd: str, command: str) -> bool:
    if rule.get("tool") != tool or not rule.get("folder") or not _under(cwd, rule["folder"]):
        return False
    if tool == "Bash":
        words = command.split()
        # A command chain or substitution is never covered by a first-word rule.
        if any(mark in command for mark in (";", "&&", "||", "|", "`", "$(", ">", "\n")):
            return False
        return bool(words) and words[0] == rule.get("prefix")
    return True


def rules(base: Path) -> list[dict[str, str]]:
    try:
        data = json.loads((base / "rules.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _save_rules(base: Path, rows: list[dict[str, str]]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(base / "rules.json", json.dumps(rows, indent=2))


def remove_rule(base: Path, index: int) -> list[dict[str, str]]:
    rows = rules(base)
    if not 0 <= index < len(rows):
        raise ValueError("There is no such approval rule.")
    del rows[index]
    _save_rules(base, rows)
    return rows


def request(base: Path, agent: str, tool: str, cwd: str, spec: dict[str, Any]) -> str:
    pending, _ = _dirs(base)
    rid = uuid.uuid4().hex[:12]
    row = {
        "id": rid,
        "agent": agent,
        "tool": tool,
        "cwd": cwd,
        "ts": time.time(),
        **describe(tool, spec),
    }
    safe_write.write_text(pending / f"{rid}.json", json.dumps(row))
    return rid


def waiting(base: Path) -> list[dict[str, Any]]:
    """Requests whose hook is still waiting, oldest first. A request older than the wait is a hook that ended."""
    pending, _ = _dirs(base)
    rows = []
    for path in pending.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if time.time() - float(row.get("ts", 0)) > WAIT_SECONDS + 30:
            path.unlink(missing_ok=True)
            continue
        row["rule"] = rule_label(rule_for(row))
        rows.append(row)
    return sorted(rows, key=lambda r: r.get("ts", 0))


def answer(base: Path, rid: object, decision: object) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(DECISIONS)}")
    found = next((r for r in waiting(base) if r["id"] == rid), None)
    if found is None:
        raise ValueError("That request is no longer waiting.")
    if decision == "folder":
        rule = rule_for(found)
        rows = rules(base)
        if rule not in rows:
            _save_rules(base, [*rows, rule])
    _, answers = _dirs(base)
    safe_write.write_text(answers / f"{rid}.json", json.dumps({"decision": decision}))
    return {"id": rid, "decision": decision, "agent": found["agent"], "tool": found["tool"]}


def deny_all(base: Path) -> int:
    """The kill switch: every waiting request is denied at once."""
    count = 0
    _, answers = _dirs(base)
    for row in waiting(base):
        safe_write.write_text(answers / f"{row['id']}.json", json.dumps({"decision": "deny"}))
        count += 1
    return count


def wait_for(base: Path, rid: str, seconds: float = WAIT_SECONDS, step: float = 0.5) -> str | None:
    """Block until the app answers. None means nobody answered in time."""
    _, answers = _dirs(base)
    target = answers / f"{rid}.json"
    deadline = time.time() + seconds
    while time.time() < deadline:
        if target.is_file():
            try:
                decision = json.loads(target.read_text(encoding="utf-8")).get("decision")
            except (OSError, ValueError):
                decision = None
            target.unlink(missing_ok=True)
            return str(decision) if decision in DECISIONS else "deny"
        time.sleep(step)
    return None


def finish(base: Path, rid: str) -> None:
    pending, _ = _dirs(base)
    (pending / f"{rid}.json").unlink(missing_ok=True)


def hook_command(base: Path, agent: str, root: Path, python: str) -> str:
    """The shell line Claude Code runs before each Bash, Edit or Write call for an agent that asks first."""
    import shlex

    return (
        f"env PYTHONPATH={shlex.quote(str(root))} {shlex.quote(python)} -m core.approval_hook "
        f"{shlex.quote(str(base))} {shlex.quote(agent)}"
    )


def settings_flag(base: Path, agent: str, root: Path, python: str) -> list[str]:
    hook = {
        "matcher": "|".join(TOOLS),
        "hooks": [
            {
                "type": "command",
                "command": hook_command(base, agent, root, python),
                "timeout": WAIT_SECONDS + 60,
            }
        ],
    }
    return ["--settings", json.dumps({"hooks": {"PreToolUse": [hook]}})]
