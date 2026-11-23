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
    account_sync,
    added_agents,
    calendar_board,
    inbox,
    pins,
    safe_write,
    search_all,
    share,
)
from core import handoff as handoff_note
from core.session_shared import (
    DELIVERY_BODY_MAX,
    _whole,
)
from core.settings import load_settings, save_engine
from core.terminal import engine_problem
from tools.vault_tools import vault_tools


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

    def handoff(self, request: dict[str, Any]) -> dict[str, Any]:
        """Hand one agent's work to another: a note in the vault's Handoffs folder (when a vault is
        open) and an inbox message to the receiving agent with the same text and a link to the note."""
        giver, taker = request.get("from"), request.get("to")
        known = self._agent_ids()
        if giver not in known or taker not in known:
            raise ValueError('"handoff" needs a "from" and a "to" agent that exist.')
        if giver == taker:
            raise ValueError("An agent cannot hand off to itself.")
        names = {"hippoherman": "Hippoherman"} | {
            str(a["id"]): str(a.get("name") or a["id"])
            for a in added_agents.load(self.agents_path)
            if a.get("id")
        }
        saved = next((a for a in added_agents.load(self.agents_path) if a.get("id") == giver), {})
        now = datetime.now()
        text = handoff_note.compose(
            now,
            names[giver],
            names[taker],
            str(request.get("note") or ""),
            [
                t
                for t in self.tasks()["tasks"]
                if t.get("assignee") == giver and t.get("status") != "done"
            ],
            cli_sessions.tool_trace(giver, handoff_note.CALLS),
            pins.paths(saved),
        )
        path = None
        if self.indexer is not None:
            path = handoff_note.path_for(now, names[giver], names[taker])
            vault_tools(self.indexer, self.lock)["create_note"].run({"path": path, "content": text})
            self.changed("notes")
        # The link goes first, so a long note cut to the message limit still points at the whole note.
        body = text if path is None else f"The note: [[{path.removesuffix('.md')}]]\n\n{text}"
        message = inbox.send(
            self.hive_path,
            inbox.USER,
            taker,
            f"Handoff from {names[giver]}",
            body[:DELIVERY_BODY_MAX],
            act="request",
            work="handoff",
        )
        self.changed("inbox")
        self.note("handoff", text=f"handed {names[giver]}'s work to {names[taker]}")
        return {"note": path, "message": message}

    def search_all(self, request: dict[str, Any]) -> dict[str, Any]:
        """One search over notes, messages, tasks, calendar events and agents (N.01)."""
        query = str(request.get("query") or "")[:200]
        if self.indexer is not None:
            with self.lock:
                titled = self.indexer.store.search(query, 50) if query.strip() else []
                paths = sorted(self.indexer.store.note_states())
            vault = self.indexer.vault
        else:
            titled, paths, vault = [], [], None
        return search_all.everything(
            query,
            search_all.notes(query, titled, vault, paths),
            inbox.all_messages(self.hive_path),
            self.tasks()["tasks"],
            calendar_board.load(self.events_path),
            [{"id": "hippoherman", "name": "Hippoherman"}, *added_agents.load(self.agents_path)],
        )

    def share_note(self, request: dict[str, Any]) -> dict[str, Any]:
        """A password link to one note (14.04). Needs a signed-in account; the link opens on the website."""
        password = request.get("password")
        if not isinstance(password, str):
            raise ValueError('"password" must be text')
        minutes = _whole(request.get("minutes", share.DEFAULT_MINUTES), "minutes")
        share.expiry(password, minutes)
        if not self.user_account.status().get("signed_in"):
            share.request_link(password, minutes)  # raises Not set up: links need an account
        text = self.note_text({"path": request.get("path")})["text"]
        title = Path(str(request.get("path") or "Note")).stem
        return self.user_account.share_create(title, text, password, minutes)

    # The account's sync and links (14.02, 14.04, 14.07); each runs only on the user's button press.
    def user_sync_save(self, request: dict[str, Any]) -> dict[str, Any]:
        return account_sync.save(
            self.user_account, self.agents_path, self.settings_path, self.storage / "usage.jsonl"
        )

    def user_sync_fetch(self, request: dict[str, Any]) -> dict[str, Any]:
        got = account_sync.fetch(self.user_account, self.agents_path, self.settings_path)
        self.settings = load_settings(self.settings_path)
        return got

    def user_shares(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"shares": self.user_account.shares()}

    def user_share_delete(self, request: dict[str, Any]) -> dict[str, Any]:
        self.user_account.share_delete(str(request.get("id") or ""))
        return self.user_shares(request)

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
