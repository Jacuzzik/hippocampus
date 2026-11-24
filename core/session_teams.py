"""Backend calls for Teams (D.07): see core/teams.py. Each call runs when the person presses a button."""

import json
from pathlib import Path
from typing import Any

from core import added_agents, teams


class TeamsPart:
    def _teams(self) -> teams.Teams:
        if not self.user_account.status().get("signed_in"):
            raise ValueError(
                "Sign in first, under Settings, Account. Each person in a team has their own sign-in."
            )
        return teams.Teams(self.user_account._data)  # noqa: SLF001 (the account's own signed-in request)

    def teams_state(self, request: dict[str, Any]) -> dict[str, Any]:
        status = self.user_account.status()
        if not status.get("signed_in"):
            return {"signed_in": False, "configured": bool(status.get("configured")), "teams": []}
        found = self._teams().mine()
        team = request.get("team")
        view: dict[str, Any] = {"signed_in": True, "configured": True, "teams": found}
        if isinstance(team, str) and any(t["id"] == team for t in found):
            service = self._teams()
            items = service.items(team)
            view["members"] = service.members(team)
            view["shared"] = {
                "agents": _names(items, "agents"),
                "tasks": _titles(items),
                "notes": [i["name"] for i in items if i["kind"] == "note"],
            }
        return view

    def team_create(self, request: dict[str, Any]) -> dict[str, Any]:
        self._teams().create(request.get("name"))
        self.note("setting", text="made a team")
        return self.teams_state({})

    def team_join(self, request: dict[str, Any]) -> dict[str, Any]:
        self._teams().join(request.get("code"))
        self.note("setting", text="joined a team")
        return self.teams_state({})

    def team_leave(self, request: dict[str, Any]) -> dict[str, Any]:
        self._teams().leave(request.get("team"))
        return self.teams_state({})

    def team_save(self, request: dict[str, Any]) -> dict[str, Any]:
        """Upload this computer's agents, task titles and Team-folder notes to the team."""
        service, team = self._teams(), request.get("team")
        service.put(team, "agents", "", teams.shared_agents(self.agents_path))
        tasks = self.tasks()["tasks"]
        service.put(
            team,
            "tasks",
            "",
            json.dumps(
                [{k: t.get(k) for k in ("id", "title", "status", "assignee")} for t in tasks]
            ),
        )
        notes = teams.team_notes(Path(self.settings.vault)) if self.settings.vault else {}
        for name, text in notes.items():
            service.put(team, "note", name, text)
        self.note("setting", text="saved to the team")
        return {
            "agents": len(added_agents.load(self.agents_path)),
            "tasks": len(tasks),
            "notes": len(notes),
        }

    def team_get(self, request: dict[str, Any]) -> dict[str, Any]:
        """Download the team's agents (new ones only) and notes (into the vault's Team folder)."""
        items = self._teams().items(request.get("team"))
        added: list[str] = []
        written = kept = 0
        for item in items:
            if item["kind"] == "agents":
                added = teams.merge_agents(self.agents_path, item["body"])
            elif item["kind"] == "note":
                if not self.settings.vault:
                    raise ValueError("Open a vault first.")
                if teams.write_note(Path(self.settings.vault), item["name"], item["body"]):
                    written += 1
                else:
                    kept += 1
        if written:
            self.changed("notes")
        self.note("setting", text="got from the team")
        return {"agents_added": added, "notes_written": written, "notes_unchanged": kept}


def _names(items: list[dict[str, str]], kind: str) -> list[str]:
    for item in items:
        if item["kind"] == kind:
            try:
                return [str(a.get("name") or a.get("id")) for a in json.loads(item["body"])]
            except (ValueError, AttributeError):
                return []
    return []


def _titles(items: list[dict[str, str]]) -> list[str]:
    for item in items:
        if item["kind"] == "tasks":
            try:
                return [f"{t.get('title')} ({t.get('status')})" for t in json.loads(item["body"])]
            except (ValueError, AttributeError):
                return []
    return []
