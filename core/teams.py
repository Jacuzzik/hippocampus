"""Teams (D.07): people who share the same agents, tasks and notes, each with their own sign-in.

Built on the account service (Supabase) the app already uses for sync. It runs only when a person presses a
button: Save to team uploads, Get from team downloads. Keys, settings and the rest of the vault never leave this
computer. The tables and rules are in supabase/migrations/20261124_teams.sql, which the project owner applies once;
until then every call says the team service is not set up yet.

  agents  the shared agents' names, models and goals (never a folder on this computer or a command)
  tasks   the task titles and statuses, to look at
  notes   the notes in the vault's Team folder
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import added_agents, safe_write

FOLDER = "Team"
NOTES_MAX = 200
NOTE_BYTES = 200_000
UUID = re.compile(r"^[0-9a-f-]{36}$")
CODE = re.compile(r"^[0-9a-f]{12}$")
# What of an added agent is shared: no folder, no custom command, nothing that is local to this computer.
AGENT_KEYS = ("id", "name", "description", "provider", "model", "goal", "autonomy", "shell")

Data = Callable[..., Any]


def _team_id(value: object) -> str:
    text = str(value or "")
    if not UUID.match(text):
        raise ValueError("That is not a team id.")
    return text


def _explain(error: ValueError) -> ValueError:
    text = str(error)
    if "404" in text or "does not exist" in text or "Could not find" in text:
        return ValueError(
            "The team service is not set up on this account yet. The project owner applies "
            "supabase/migrations/20261124_teams.sql once, then teams work."
        )
    return error


class Teams:
    def __init__(self, data: Data) -> None:
        self.data = data

    def _do(self, *args: object, **kwargs: object) -> Any:  # noqa: ANN401 (the account's own JSON answer)
        try:
            return self.data(*args, **kwargs)
        except ValueError as error:
            raise _explain(error) from error

    def mine(self) -> list[dict[str, Any]]:
        rows = self._do(
            "/rest/v1/team_members?select=role,teams(id,name,join_code)&order=joined_at",
            method="GET",
        )
        out = []
        for row in rows or []:
            team = row.get("teams") or {}
            if team.get("id"):
                out.append(
                    {
                        "id": team["id"],
                        "name": team.get("name", ""),
                        "role": row.get("role", "member"),
                        # Only an owner is shown the code to give to a teammate.
                        "code": team.get("join_code", "") if row.get("role") == "owner" else "",
                    }
                )
        return out

    def create(self, name: object) -> dict[str, Any]:
        text = " ".join(str(name or "").split())
        if not 1 <= len(text) <= 80:
            raise ValueError("Give the team a name of up to 80 characters.")
        rows = self._do("/rest/v1/rpc/create_team", {"p_name": text})
        return rows[0] if isinstance(rows, list) and rows else {}

    def join(self, code: object) -> dict[str, Any]:
        text = str(code or "").strip().lower()
        if not CODE.match(text):
            raise ValueError("A team code is 12 letters and digits. Ask the team's owner for it.")
        rows = self._do("/rest/v1/rpc/join_team", {"p_code": text})
        return rows[0] if isinstance(rows, list) and rows else {}

    def leave(self, team: object) -> None:
        self._do("/rest/v1/rpc/leave_team", {"p_team": _team_id(team)})

    def members(self, team: object) -> list[dict[str, str]]:
        tid = _team_id(team)
        rows = self._do(
            f"/rest/v1/team_members?team_id=eq.{tid}&select=email,role&order=joined_at",
            method="GET",
        )
        return [{"email": r.get("email", ""), "role": r.get("role", "")} for r in rows or []]

    def put(self, team: object, kind: str, name: str, body: str) -> None:
        tid = _team_id(team)
        self._do(
            "/rest/v1/team_items?on_conflict=team_id,kind,name",
            [{"team_id": tid, "kind": kind, "name": name, "body": body}],
            prefer="resolution=merge-duplicates",
        )

    def items(self, team: object) -> list[dict[str, str]]:
        tid = _team_id(team)
        rows = self._do(
            f"/rest/v1/team_items?team_id=eq.{tid}&select=kind,name,body,updated_at&order=updated_at.desc",
            method="GET",
        )
        return [dict(r) for r in rows or []]


def shared_agents(agents: Path) -> str:
    rows = [
        {k: a[k] for k in AGENT_KEYS if k in a} for a in added_agents.load(agents) if a.get("id")
    ]
    return json.dumps(rows)


def merge_agents(agents: Path, incoming: str) -> list[str]:
    """Add the team's agents this computer does not have yet (matched by id). Existing agents are untouched."""
    have = added_agents.load(agents)
    known = {a.get("id") for a in have}
    fresh = [
        {**a, "folder": ""}
        for a in json.loads(incoming)
        if isinstance(a, dict) and a.get("id") and a["id"] not in known
    ]
    if fresh:
        added_agents.save(agents, [*have, *fresh])
    return [str(a.get("name") or a["id"]) for a in fresh]


def team_notes(vault: Path) -> dict[str, str]:
    folder = vault / FOLDER
    out: dict[str, str] = {}
    if not folder.is_dir():
        return out
    for path in sorted(folder.rglob("*.md"))[:NOTES_MAX]:
        if path.is_file() and path.stat().st_size <= NOTE_BYTES:
            out[path.relative_to(vault).as_posix()] = path.read_text(
                encoding="utf-8", errors="replace"
            )
    return out


def write_note(vault: Path, name: str, text: str) -> bool:
    """Write a team note under the vault's Team folder. A note you changed after the team's copy is kept."""
    target = (vault / name).resolve()
    if (
        not name.startswith(f"{FOLDER}/")
        or not name.endswith(".md")
        or (vault / FOLDER).resolve() not in target.parents
    ):
        raise ValueError(f"{name} is not a note in the Team folder.")
    if target.is_file() and target.read_text(encoding="utf-8", errors="replace") == text:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        safe_write.write_text(
            target.with_name(target.stem + " (yours).md"), target.read_text(encoding="utf-8")
        )
    safe_write.write_text(target, text)
    return True
