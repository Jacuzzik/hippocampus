"""Added agents, their folders, tasks sent to them and sharing a note."""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from ai import chat_history, cli_sessions
from core import (
    added_agents,
    inbox,
    safe_write,
    share,
)
from core.session_shared import (
    _whole,
)
from core.settings import load_settings, save_engine
from core.terminal import engine_problem


class AgentsPart:
    def agents_state(self) -> dict[str, Any]:
        return {"agents": added_agents.load(self.agents_path)}

    def save_agents(self, request: dict[str, Any]) -> dict[str, Any]:
        agents = request.get("agents")
        previous = added_agents.load(self.agents_path)
        added_agents.save(self.agents_path, agents)
        # Archived ids come from the app's own list; without them, the last saved set is kept.
        archived_path = self.storage / "agents_archived.json"
        if isinstance(request.get("archived"), list):
            archived_path.write_text(
                json.dumps([str(x) for x in request["archived"]]), encoding="utf-8"
            )
        archived = (
            set(json.loads(archived_path.read_text(encoding="utf-8")))
            if archived_path.exists()
            else set()
        )
        self._write_agent_list(previous, agents, archived)
        return {"agents": agents}

    def _write_agent_list(
        self, previous: list[dict[str, Any]], current: list[dict[str, Any]], archived: set[str]
    ) -> None:
        # Keeps the Agent Lists note in step with the app: active agents, and every agent removed since it was added.
        removed_path = self.storage / "agents_removed.json"
        removed = (
            json.loads(removed_path.read_text(encoding="utf-8")) if removed_path.exists() else []
        )
        now_ids = {a["id"] for a in current}
        known = {r["id"] for r in removed}
        stamp = datetime.now().date().isoformat()
        removed += [
            {"id": a["id"], "name": a["name"], "removed": stamp}
            for a in previous
            if a["id"] not in now_ids and a["id"] not in known
        ]
        safe_write.write_text(removed_path, json.dumps(removed, indent=2))
        vault = self.settings.vault
        if not vault or not Path(vault).is_dir():
            return
        active = [a for a in current if a["id"] not in archived]
        hidden = [a for a in current if a["id"] in archived]
        lines = [
            "# Agent Lists",
            "",
            "Every agent in the app: what it does, its status and where its memory is kept. One note per agent, linked here. Only the user can edit, delete or remove these notes.",
            "",
            "## Active",
        ]
        # Tokens are counted per folder this month, so two agents in one folder share a figure.
        lines += [
            f"- {a['name']}: {a.get('description') or 'no description yet'} ({a.get('provider', 'no provider')}, model {a.get('model') or 'default'}, folder {a.get('folder') or 'not set'}, tokens this month {cli_sessions.folder_tokens(a['folder']) if a.get('folder') else 0})"
            for a in active
        ] or ["- None yet."]
        lines += ["", "## Archived"]
        lines += [
            f"- {a['name']}: {a.get('description') or 'no description yet'}" for a in hidden
        ] or ["- None."]
        lines += ["", "## Deleted"]
        lines += [f"- {r['name']}, removed {r['removed']}" for r in removed] or ["- None."]
        (Path(vault) / "Agent Lists.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    @property
    def agents_path(self) -> Path:
        return self.storage / "agents.json"

    def task_send(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send a message to one agent, or to all of them with to "all". `from` is "user" for the human's own
        compose box; anything else is sent as the main agent."""
        to = str(request.get("to") or "").strip()
        if not to:
            raise ValueError('"task_send" needs a "to" agent id')
        sender = inbox.USER if request.get("from") == inbox.USER else "hippoherman"
        known = self._agent_ids()
        targets = sorted(known - {sender}) if to == "all" else [to]
        if to != "all" and to not in known:
            raise ValueError(f'No agent has the id "{to}".')
        fields = {
            "act": str(request.get("act") or "request"),
            "work": str(request.get("work") or ""),
            "reply_to": str(request.get("replyTo") or ""),
            "priority": str(request.get("priority") or "normal"),
        }
        ids = [
            inbox.send(
                self.hive_path,
                sender,
                target,
                str(request.get("subject") or ""),
                str(request.get("body") or ""),
                **fields,
            )
            for target in targets
        ]
        self.changed("inbox")
        return {"id": ids[0] if ids else None, "ids": ids}

    def share_note(self, request: dict[str, Any]) -> dict[str, Any]:
        password = request.get("password")
        if not isinstance(password, str):
            raise ValueError('"password" must be text')
        minutes = _whole(request.get("minutes", share.DEFAULT_MINUTES), "minutes")
        share.request_link(password, minutes)  # always raises until a share host is set up
        return {}

    # Folders an agent can work in: each one inside the app's workspaces folder.
    def workspaces(self) -> dict[str, Any]:
        root = self.storage.parent / "workspaces"
        root.mkdir(parents=True, exist_ok=True)
        names = sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
        return {"root": str(root.resolve()), "folders": names}

    def create_workspace(self, request: dict[str, Any]) -> dict[str, Any]:
        # A plain folder name only, so the new folder always lands directly inside workspaces.
        name = str(request.get("name") or "").strip()
        if not name or len(name) > 64 or name.startswith(".") or "/" in name or "\\" in name:
            raise ValueError("Use a folder name without slashes, up to 64 characters.")
        root = self.storage.parent / "workspaces"
        folder = root / name
        if folder.exists():
            raise ValueError(f'A folder named "{name}" already exists.')
        folder.mkdir(parents=True)
        return {
            "root": str(root.resolve()),
            "folders": sorted(p.name for p in root.iterdir() if p.is_dir()),
        }

    def agent_session(self, request: dict[str, Any]) -> dict[str, Any]:
        # The agent's folder is created here; a relative name is made inside the vault.
        folder = str(request.get("folder") or "").strip()
        resolved = None
        if folder:
            path = Path(folder).expanduser()
            if not path.is_absolute():
                path = (self.settings.vault or Path.home()) / path
            path.mkdir(parents=True, exist_ok=True)
            resolved = str(path.resolve())
        return {"session": cli_sessions.get(request["agent"])["id"], "folder": resolved}

    def git_status(self, request: dict[str, Any]) -> dict[str, Any]:
        """The short git status of an agent's folder, for its Git view."""
        folder = request.get("folder")
        if not isinstance(folder, str) or not os.path.isdir(folder):
            raise ValueError("the agent's folder does not exist yet")
        done = subprocess.run(
            ["git", "-C", folder, "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if done.returncode != 0:
            return {"text": "This folder is not a git repository."}
        return {"text": done.stdout.strip() or "Nothing to commit."}

    def open_folder(self, request: dict[str, Any]) -> dict[str, Any]:
        """Opens an agent's folder in the file manager ("file") or in VS Code ("ide")."""
        folder = request.get("folder")
        if not isinstance(folder, str) or not os.path.isdir(folder):
            raise ValueError("the agent's folder does not exist yet")
        command = "code" if request.get("app") == "ide" else "xdg-open"
        binary = shutil.which(command)
        if binary is None:
            raise RuntimeError(f"{command} is not installed on this computer")
        subprocess.Popen(
            [binary, folder],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"ok": True}

    def chat_history_load(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"sessions": chat_history.load(request["agent"])}

    def chat_history_store(self, request: dict[str, Any]) -> dict[str, Any]:
        chat_history.save(request["agent"], request.get("sessions"))
        return {"saved": True}

    def current_session(self, request: dict[str, Any]) -> dict[str, Any]:
        """The agent's existing Claude session, kept as it is. Used when the chat window opens with no saved history."""
        return {"session": cli_sessions.get(request["agent"])["id"]}

    def new_session(self, request: dict[str, Any]) -> dict[str, Any]:
        cli_sessions.switch(request["agent"])
        return {"session": cli_sessions.get(request["agent"])["id"]}

    def tokens(self, request: dict[str, Any]) -> dict[str, Any]:
        folders = [str(f) for f in request.get("folders") or [] if f]
        return {
            "folders": {f: cli_sessions.folder_tokens(f) for f in folders},
            "activity": {f: cli_sessions.folder_activity(f) for f in folders},
        }

    def set_engine(self, request: dict[str, Any]) -> dict[str, Any]:
        provider, model = str(request.get("provider") or ""), str(request.get("model") or "")
        # The provider must be usable here (CLI installed, key saved, server running); otherwise nothing changes.
        problem = engine_problem(provider) if provider else None
        if problem:
            return {"ok": False, "error": problem}
        try:
            save_engine(provider, model, self.settings_path)
            self.settings = load_settings(self.settings_path)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "message": f"Saved: main agent now uses {provider} {model}. Its terminal restarts with it.",
        }

    def engine(self) -> dict[str, Any]:
        ai = self.settings
        return {
            "provider": ai.provider,
            "model": ai.claude_model if ai.provider == "claude" else ai.provider_model,
            "folder": str(ai.vault or ""),
        }
