"""Backend calls for features that were Planned: the update check (G.04), calendars by their private iCal
address, Notion pages into notes, search by meaning (7.09) and plugins (D.07)."""

import base64
import binascii
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from keyring.errors import KeyringError

from ai import keys, network
from core import (
    added_agents,
    briefing,
    code_editor,
    demo_vault,
    ical_feed,
    notion,
    safe_write,
    semantic,
    updates,
    usage_stats,
)
from core.plugins import Plugins
from core.session_shared import KEYCHAIN_MISSING
from tools.vault_tools import vault_tools

CALENDAR = "calendar-ical"
NOTION = "notion"
CAPTURE_NOTE = "Inbox.md"


def _outbound(what: str) -> None:
    if network.mode() not in ("converse", "open"):
        raise ValueError(
            f"The network is {network.mode().capitalize()}, so {what} cannot be reached. "
            "Change it in Settings, Agents."
        )


def _store_key(name: str, value: str) -> None:
    try:
        keys.set_key(name, value)
    except KeyringError as error:
        raise ValueError(KEYCHAIN_MISSING) from error


def _clear_key(name: str) -> None:
    try:
        keys.clear_key(name)
    except KeyringError as error:
        raise ValueError(KEYCHAIN_MISSING) from error


class ExtrasPart:
    # Prefs for these features, apart from keys (which live in the keychain).
    @property
    def extras_path(self) -> Path:
        return self.storage / "extras.json"

    def _extras(self) -> dict[str, Any]:
        try:
            data = json.loads(self.extras_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _extras_save(self, **values: object) -> None:
        safe_write.write_text(self.extras_path, json.dumps({**self._extras(), **values}, indent=2))

    # Update check
    def update_state(self) -> dict[str, Any]:
        saved = self._extras()
        return {
            "on": bool(saved.get("update_check")),
            "current": updates.__version__,
            "last": saved.get("update_last") or None,
            "page": updates.PAGE,
        }

    def update_set(self, request: dict[str, Any]) -> dict[str, Any]:
        on = request.get("on")
        if not isinstance(on, bool):
            raise ValueError('"update_set" needs "on": true or false')
        self._extras_save(update_check=on)
        self.note("setting", text=f"update check turned {'on' if on else 'off'}")
        return self.update_state()

    def update_check(self) -> dict[str, Any]:
        if not self._extras().get("update_check"):
            raise ValueError("The update check is off. Turn it on first.")
        _outbound("GitHub")
        found = updates.check(self.__dict__.get("_update_get", updates.http_get))
        found["checked"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self._extras_save(update_last=found)
        return self.update_state()

    # Calendars
    def calendar_link_state(self) -> dict[str, Any]:
        saved = self._extras()
        return {
            "connected": keys.get_key(CALENDAR) is not None,
            "name": saved.get("calendar_name", ""),
            "events": saved.get("calendar_events") or [],
            "read_at": saved.get("calendar_read_at", ""),
        }

    def calendar_link_set(self, request: dict[str, Any]) -> dict[str, Any]:
        link = ical_feed.check_link(request.get("url"))
        name = str(request.get("name") or "My calendar").strip()[:60] or "My calendar"
        _store_key(CALENDAR, link)
        self._extras_save(calendar_name=name)
        self.note("setting", text=f"connected the calendar {name}")
        return self.calendar_read()

    def calendar_link_clear(self) -> dict[str, Any]:
        _clear_key(CALENDAR)
        self._extras_save(calendar_events=[], calendar_read_at="", calendar_name="")
        return self.calendar_link_state()

    def calendar_read(self) -> dict[str, Any]:
        link = keys.get_key(CALENDAR)
        if link is None:
            raise ValueError("No calendar is connected.")
        _outbound("the calendar")
        now = datetime.now().astimezone()
        get = self.__dict__.get("_calendar_get", ical_feed.http_get)
        events = ical_feed.read(link, now.date(), now.tzinfo, get)
        self._extras_save(
            calendar_events=events, calendar_read_at=now.isoformat(timespec="seconds")
        )
        return self.calendar_link_state()

    def feed_events(self) -> list[dict[str, str]]:
        """The calendar's events as last read, for the daily brief. Read again when older than an hour."""
        state = self.calendar_link_state()
        if not state["connected"]:
            return []
        try:
            read_at = datetime.fromisoformat(state["read_at"]) if state["read_at"] else None
            if read_at is None or (datetime.now().astimezone() - read_at).total_seconds() > 3600:
                state = self.calendar_read()
        except (ValueError, OSError):
            pass
        return list(state["events"])

    # Notion
    def notion_state(self) -> dict[str, Any]:
        return {"connected": keys.get_key(NOTION) is not None, "folder": notion.FOLDER}

    def notion_connect(self, request: dict[str, Any]) -> dict[str, Any]:
        token = notion.check_token(request.get("token"))
        _outbound("Notion")
        call = self.__dict__.get("_notion_call", notion.http_call)
        call(token, "GET", "/users/me", None)  # a wrong secret is refused here, before it is kept
        _store_key(NOTION, token)
        self.note("setting", text="connected Notion")
        return self.notion_state()

    def notion_disconnect(self) -> dict[str, Any]:
        _clear_key(NOTION)
        return self.notion_state()

    def _notion_token(self) -> str:
        token = keys.get_key(NOTION)
        if token is None:
            raise ValueError("Notion is not connected.")
        _outbound("Notion")
        return token

    def notion_search(self, request: dict[str, Any]) -> dict[str, Any]:
        call = self.__dict__.get("_notion_call", notion.http_call)
        return {
            "results": notion.search(self._notion_token(), str(request.get("query") or ""), call)
        }

    def notion_import(self, request: dict[str, Any]) -> dict[str, Any]:
        call = self.__dict__.get("_notion_call", notion.http_call)
        title, text = notion.page_markdown(self._notion_token(), str(request.get("id") or ""), call)
        path = notion.note_path(title)
        if self.indexer is None:
            raise ValueError("Open a vault first.")
        tools = vault_tools(self.indexer, self.lock)
        try:
            tools["edit_note"].run({"path": path, "content": text})
        except FileNotFoundError:
            tools["create_note"].run({"path": path, "content": text})
        self.changed("notes")
        self.note("setting", text=f"read the Notion page {title} into {path}")
        return {"path": path, "title": title}

    # Search by meaning
    @property
    def embeddings_path(self) -> Path:
        return self.storage / "embeddings.json"

    def semantic_state(self) -> dict[str, Any]:
        return semantic.state(self.embeddings_path)

    def semantic_build(self) -> dict[str, Any]:
        if not self.settings.vault:
            raise ValueError("Open a vault first.")
        embed = self.__dict__.get("_embed", semantic.ollama_embed)
        done = semantic.build(Path(self.settings.vault), self.embeddings_path, embed)
        return {**self.semantic_state(), **done}

    def semantic_search(self, request: dict[str, Any]) -> dict[str, Any]:
        embed = self.__dict__.get("_embed", semantic.ollama_embed)
        return {
            "results": semantic.search(str(request.get("query") or ""), self.embeddings_path, embed)
        }

    # Plugins
    @property
    def plugins(self) -> Plugins:
        return Plugins(self.storage)

    def plugin_list(self) -> dict[str, Any]:
        return {"plugins": self.plugins.rows()}

    def plugin_install(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            data = base64.b64decode(str(request.get("data") or ""), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("The file could not be read.") from error
        rows = self.plugins.install(str(request.get("name") or ""), data)
        self.note("setting", text=f"installed a plugin from {request.get('name')}")
        return {"plugins": rows}

    def plugin_enable(self, request: dict[str, Any]) -> dict[str, Any]:
        on = request.get("on")
        if not isinstance(on, bool):
            raise ValueError('"plugin_enable" needs "on": true or false')
        return {"plugins": self.plugins.set_enabled(str(request.get("name") or ""), on)}

    def plugin_remove(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"plugins": self.plugins.remove(str(request.get("name") or ""))}

    # Briefing builder (N.05) and trail notes (N.04)
    def briefing_build(self, request: dict[str, Any]) -> dict[str, Any]:
        agent = str(request.get("agent") or "")
        saved = next((a for a in added_agents.load(self.agents_path) if a.get("id") == agent), None)
        if saved is None and agent != "hippoherman":
            raise ValueError("No agent has that id.")
        saved = saved or {}
        provider = str(saved.get("provider") or "claude")
        folder = str(saved.get("folder") or "") or (
            str(self.settings.vault) if self.settings.vault else None
        )
        text, mark, _inbox, blocks = self.compose_briefing(
            agent, provider, folder, saved, bool(saved.get("block_tools")), write_inbox=False
        )
        return {
            "agent": agent,
            "text": text,
            "size": len(text),
            "limit": briefing.SIZE_MAX,
            "blocks": blocks,
            "problems": briefing.lint(text),
            "version": mark["version"],
            "hash": mark["hash"],
        }

    def briefing_blocks_set(self, request: dict[str, Any]) -> dict[str, Any]:
        block = request.get("block")
        on = request.get("on")
        if block not in ("pinned", "handoff", "trail") or not isinstance(on, bool):
            raise ValueError(
                '"briefing_blocks_set" needs a "block" (pinned, handoff or trail) and "on"'
            )
        off = set(self._extras().get("briefing_off") or [])
        (off.discard if on else off.add)(block)
        self._extras_save(briefing_off=sorted(off))
        self.note("setting", text=f"briefing block {block} turned {'on' if on else 'off'}")
        return self.briefing_build(request)

    def trail_notes(self) -> dict[str, Any]:
        if not self.settings.vault:
            return {"rows": [], "on": False}
        agents = [str(a.get("id")) for a in added_agents.load(self.agents_path) if a.get("id")]
        on = "trail" not in set(self._extras().get("briefing_off") or [])
        return {"rows": briefing.trails(self.settings.vault, agents), "on": on}

    # Quick capture (N.17)
    def capture(self, request: dict[str, Any]) -> dict[str, Any]:
        text = " ".join(str(request.get("text") or "").split())[:2000]
        if not text:
            raise ValueError("Type the thought to keep.")
        if not self.settings.vault:
            raise ValueError("Open a vault first.")
        agent = " ".join(str(request.get("agent") or "").split())[:60]
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
        line = f"- {stamp}{f' ({agent})' if agent else ''}: {text}\n"
        path = Path(self.settings.vault) / CAPTURE_NOTE
        with self.lock:
            old = (
                path.read_text(encoding="utf-8")
                if path.is_file()
                else ("# Inbox\n\nQuick thoughts, newest last. Linked to [[Summaries]].\n\n")
            )
            safe_write.write_text(path, old + ("" if old.endswith("\n") else "\n") + line)
        self.changed("notes")
        return {"path": CAPTURE_NOTE, "line": line.strip()}

    # Demo vault and first-run tour (N.26)
    def demo_state(self) -> dict[str, Any]:
        vault = self.settings.vault
        return {
            "in_demo": demo_vault.is_demo(self.storage, vault),
            "notes": len(demo_vault.NOTES),
            "label": demo_vault.LABEL,
            "return_to": self._extras().get("demo_return") or None,
        }

    def demo_open(self) -> dict[str, Any]:
        vault = self.settings.vault
        if not demo_vault.is_demo(self.storage, vault):
            self._extras_save(demo_return=str(vault) if vault else None)
        folder = demo_vault.build(self.storage)
        self.set_vault({"vault": str(folder)})
        self.changed("notes")
        return self.demo_state()

    def demo_leave(self) -> dict[str, Any]:
        back = self._extras().get("demo_return")
        if not back or not Path(back).is_dir():
            raise ValueError(
                "There is no earlier vault to go back to. Choose a folder in Settings."
            )
        self.set_vault({"vault": back})
        self._extras_save(demo_return=None)
        self.changed("notes")
        return self.demo_state()

    # Usage statistics, local only (7.31)
    def usage_stats(self) -> dict[str, Any]:
        return usage_stats.summarize(self.storage)

    # Built-in code editor (7.18): files and git inside one agent's folder
    def editor_tree(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"rows": code_editor.tree(request.get("folder"), str(request.get("path") or ""))}

    def editor_read(self, request: dict[str, Any]) -> dict[str, Any]:
        return code_editor.read(request.get("folder"), request.get("path"))

    def editor_save(self, request: dict[str, Any]) -> dict[str, Any]:
        saved = code_editor.save(request.get("folder"), request.get("path"), request.get("text"))
        self.note("setting", text=f"editor saved {saved['path']}")
        return saved

    def editor_git(self, request: dict[str, Any]) -> dict[str, Any]:
        found = code_editor.changes(request.get("folder"))
        found["branches"] = code_editor.branches(request.get("folder")) if found["repo"] else []
        return found

    def editor_diff(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"text": code_editor.diff(request.get("folder"), request.get("path"))}

    def editor_history(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"rows": code_editor.history(request.get("folder"), str(request.get("path") or ""))}

    def editor_compare(self, request: dict[str, Any]) -> dict[str, Any]:
        return code_editor.compare(request.get("folder"), request.get("base"), request.get("head"))
