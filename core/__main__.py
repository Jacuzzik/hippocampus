"""Sidecar entry point.

`serve` runs the JSON-lines bridge the Tauri shell talks to. It prints a ready line,
then reads one JSON request per line on stdin and answers each with one line on stdout.
Requests: {"id": ..., "method": "graph"}, {"id": ..., "method": "open", "vault": "<folder>"} and
{"id": ..., "method": "read", "path": "<note id>"} (answers {"id": <note id>, "text": ...}).
{"method": "account"} answers {"claude": true|false}; {"method": "sign_in", "key": "<key>"} saves
the Claude key in the keychain and {"method": "sign_out"} removes it. Neither ever returns the key.
{"method": "remove_data"} deletes the index cache and the key; the vault is never touched.
Answers: {"id": ..., "result": ...} or {"id": ..., "error": "<message>"}. A bad line gets an
error answer and the loop keeps going. It runs until stdin closes. No network listener.

`serve` also answers {"method": "chat", "chat": <id>, "text": ...} with the assistant's
reply. While a chat runs, the sidecar prints event lines (no "id"): {"event": "tool", ...}
as tools run and {"event": "confirm", "call": ..., "preview": ...} when a write needs
approval. Answer one with {"method": "confirm", "call": ..., "approve": true|false}.
{"method": "stop"} is the kill switch.

`index` and `watch` build and maintain a vault's SQLite index. Each prints one
JSON status line on stdout and logs to stderr. `watch` runs until Ctrl+C,
SIGTERM or stdin closes.

`key set|status|clear` manages the Claude API key in the OS keychain. It never prints the key.
"""

import argparse
import asyncio
import contextlib
import getpass
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from keyring.errors import KeyringError

from ai import network
from ai.agent import Agent, AgentPaused
from ai.keys import clear_api_key, clear_key, get_api_key, get_key, key_hint, set_api_key, set_key

# The office task board the Tasks tab reads; MD_TASKS_FILE overrides it.
DEFAULT_TASKS_FILE = "/home/thalha/Documents/Obsidian/Munder-Difflin/hive/tasks.json"
DEFAULT_HIVE_DIR = "/home/thalha/Documents/Obsidian/Munder-Difflin/hive"
from ai.providers.openai_compat import PRESETS
from ai.router import build_router, model_name
from core import __version__, added_agents, share, skills, webhooks
from core import activity as journal
from core import budget as budgets
from core import jobs as job_store
from core import memory as memory_notes
from core.cards import CardStore
from core.helpers import HelperLimit, Helpers
from core.settings import (
    CAP_WINDOWS,
    SETTINGS_PATH,
    Caps,
    Settings,
    load_settings,
    save_allowed_tools,
    save_budget,
    save_network_mode,
    save_vault,
)
from core.vault import Indexer, open_index
from core.vault.scanner import iter_notes
from core.vault.watcher import VaultWatcher
from tools.gate import AskQueue, ConfirmGate, KillSwitch, Stopped
from tools.registry import CONFIRM_TIERS
from tools.vault_tools import vault_tools

logger = logging.getLogger("hippocampus.core")

DEFAULT_STORAGE = Path(__file__).resolve().parent.parent / "storage"
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
SCHEDULE_SECONDS = 60
KEYCHAIN_MISSING = (
    "the OS keychain is not available. Install a Secret Service keyring "
    "(for example GNOME Keyring or KWallet), then try again."
)


Emit = Callable[[dict[str, Any]], None]


class Session:
    """The vault the serve loop has open, the assistant, and the requests they answer.

    `lock` guards the SQLite store, which the chat's tools share with the requests.
    """

    def __init__(
        self,
        storage: Path,
        settings: Settings | None = None,
        emit: Emit | None = None,
        settings_path: Path = SETTINGS_PATH,
    ) -> None:
        self.storage = storage
        self.settings_path = settings_path
        self.settings = settings if settings is not None else load_settings(settings_path)
        self.emit: Emit = emit or (lambda _event: None)
        self.indexer: Indexer | None = None
        self.cards = CardStore(storage / "cards")
        self.lock = threading.RLock()
        self.kill = KillSwitch()
        self.gate = ConfirmGate()
        self.asks = AskQueue()
        self.paused: list[dict[str, Any]] | None = (
            None  # messages of a request that hit its tool limit
        )
        self.allowance = False  # the user allowed one request past a budget cap
        self.embedder: memory_notes.Embedder | None = (
            None  # none installed: search by meaning is off
        )
        self.ledger = budgets.Ledger(storage / "usage.jsonl")
        self.helpers = Helpers(self._helper_run, lambda e: self.note("handoff", text=e["text"]))
        network.set_mode(self.settings.network_mode)

    def open(self, vault: Path) -> dict[str, Any]:
        if not vault.is_dir():
            raise ValueError(f"vault folder not found: {vault}")
        with self.lock:
            self.close()
            self.indexer = open_index(vault, self.storage)
            stats = self.indexer.full_sync()
            self.trim_memory()
            status = {f"{k}_files": getattr(stats, k) for k in stats.__slots__}
            return {"vault": str(vault.resolve()), **self.indexer.store.counts(), **status}

    def account(self) -> dict[str, Any]:
        # Only whether a key is saved and the model name; the key itself never leaves the keychain.
        api_key = get_api_key()
        return {"claude": api_key is not None, "model": model_name(self.settings, api_key)}

    def tasks(self) -> dict[str, Any]:
        # Read-only view of the office task board. A missing or unreadable file shows no tasks.
        path = Path(os.environ.get("MD_TASKS_FILE", DEFAULT_TASKS_FILE))
        try:
            raw = json.loads(path.read_text(encoding="utf-8")).get("tasks", [])
        except (OSError, ValueError, AttributeError):
            return {"tasks": []}
        keep = ("id", "title", "status", "assignee", "updatedAt")
        return {"tasks": [{k: t.get(k) for k in keep} for t in raw if isinstance(t, dict)]}

    def inbox(self) -> dict[str, Any]:
        # Read-only view of every agent's inbox: pending messages first, then handled ones.
        agents = Path(os.environ.get("MD_HIVE_DIR", DEFAULT_HIVE_DIR)) / "agents"
        rows: list[dict[str, Any]] = []
        for folder in sorted(p for p in agents.glob("*") if p.is_dir()):
            for path, state in ((folder / "inbox", "pending"), (folder / "inbox" / ".done", "done")):
                for file in path.glob("*.json"):
                    try:
                        msg = json.loads(file.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    if not isinstance(msg, dict):
                        continue
                    keep = ("id", "from", "to", "act", "subject", "created_at")
                    rows.append({**{k: msg.get(k) for k in keep}, "state": state})
        rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return {"messages": rows[:50]}

    def memory_notes(self) -> dict[str, Any]:
        # Read-only list of each agent's memory.md: size and last update, newest first.
        agents = Path(os.environ.get("MD_HIVE_DIR", DEFAULT_HIVE_DIR)) / "agents"
        rows: list[dict[str, Any]] = []
        for file in agents.glob("*/memory.md"):
            try:
                stat = file.stat()
            except OSError:
                continue
            rows.append({
                "agent": file.parent.name,
                "bytes": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="minutes"),
            })
        rows.sort(key=lambda r: r["updated_at"], reverse=True)
        return {"notes": rows}

    def settings_view(self) -> dict[str, Any]:
        # Read-only view of the saved settings. API keys are never included.
        s = self.settings
        return {
            "general": {"vault": str(s.vault) if s.vault else None, "network": s.network_mode},
            "agents": {
                "provider": s.provider,
                "model": s.provider_model or s.claude_model,
                "ollama": s.ollama_model,
            },
            "budgets": {
                "app": asdict(s.budget),
                "assistant": asdict(s.assistant_budget),
                "max_tool_calls": s.max_tool_calls,
            },
            "memory": {"max_bytes": s.memory_max_bytes},
        }

    def sign_in(self, request: dict[str, Any]) -> dict[str, Any]:
        key = request.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError('"sign_in" needs a non-empty "key"')
        try:
            set_api_key(key.strip())
        except KeyringError as error:
            raise ValueError(KEYCHAIN_MISSING) from error
        return {"claude": True}

    def sign_out(self) -> dict[str, Any]:
        try:
            clear_api_key()
        except KeyringError as error:
            raise ValueError(KEYCHAIN_MISSING) from error
        return {"claude": False}

    def remove_data(self) -> dict[str, Any]:
        """Delete the index cache and the Claude key. The vault is never touched."""
        self.close()
        index = self.storage / "index"
        if index.exists():
            shutil.rmtree(index)
        return self.sign_out()

    def graph(self) -> dict[str, Any]:
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            return self.indexer.store.graph()

    def read(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return a note's text. The path checks are the ones `read_note` uses."""
        path = request.get("path")
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            text = vault_tools(self.indexer, self.lock)["read_note"].run({"path": path})
        return {"id": path, "text": text}

    def chat(self, request: dict[str, Any]) -> dict[str, Any]:
        text = request.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError('"chat" needs a non-empty "text"')
        chat_id = request.get("chat")  # the UI names each chat so it can match its events
        over = None if self.allowance else self.budget_overrun()
        if over is not None:
            self.note("budget", text=f"paused: {over.scope} {over.window} cap reached")
            return {"reply": "", "stopped": False, "budget": over.as_dict()}
        self.allowance = False
        messages, self.paused = self.paused, None
        if request.get("continue") is True and messages is None:
            raise ValueError("nothing is paused to continue")
        if request.get("continue") is not True:
            messages = None
        else:
            self.note("handoff", text="continued a request paused at the tool-call limit")
        self.kill.reset()  # a stop only ends the work that was running when it was sent
        tools = vault_tools(self.indexer, self.lock) if self.indexer is not None else {}
        router = build_router(self.settings, get_api_key())

        def emit(event: dict[str, Any]) -> None:
            self.journal_event(event)
            self.emit({**event, "chat": chat_id})

        agent = Agent(
            router,
            tools,
            self.kill,
            self.gate,
            emit,
            max_tool_calls=self.settings.max_tool_calls,
            allowed=self.settings.allowed_tools,
            asks=self.asks,
        )
        try:
            reply = asyncio.run(agent.run(text.strip(), messages))
        except Stopped:
            return {"reply": "", "stopped": True}
        except AgentPaused as paused:
            self.paused = paused.messages
            self.note("handoff", text=f"paused at {paused.limit} tool calls; Continue resumes it")
            return {"reply": "", "stopped": False, "limit": paused.limit}
        finally:
            self.ledger.add("assistant", agent.tokens_used)
        return {"reply": reply, "stopped": False}

    def confirm(self, request: dict[str, Any]) -> dict[str, Any]:
        call = request.get("call")
        if not isinstance(call, str) or not self.gate.decide(call, request.get("approve") is True):
            raise ValueError("no confirmation is waiting with that call id")
        return {"call": call}

    def tools(self) -> dict[str, Any]:
        """Every tool the assistant has, and whether its allowlist lets it use each one."""
        registry = vault_tools(self.indexer, self.lock) if self.indexer is not None else {}
        allowed = self.settings.allowed_tools
        listed = [
            {"name": t.name, "tier": t.tier, "allowed": allowed is None or t.name in allowed}
            for t in registry.values()
        ]
        return {"tools": listed, "every": allowed is None}

    def set_tools(self, request: dict[str, Any]) -> dict[str, Any]:
        """Set the tool allowlist (names, or null for every tool) and save it."""
        names = request.get("names")
        if names is not None and (
            not isinstance(names, list) or not all(isinstance(n, str) for n in names)
        ):
            raise ValueError('"names" must be a list of tool names, or null for every tool')
        allowed = None if names is None else tuple(names)
        save_allowed_tools(allowed, SETTINGS_PATH)  # raises ValueError on a bad name
        self.settings = replace(self.settings, allowed_tools=allowed)
        logger.info(
            "assistant tool allowlist set to %s", "every tool" if allowed is None else allowed
        )
        return {"names": names}

    def answer(self, request: dict[str, Any]) -> dict[str, Any]:
        call, text = request.get("call"), request.get("text")
        if (
            not isinstance(call, str)
            or not isinstance(text, str)
            or not self.asks.answer(call, text)
        ):
            raise ValueError("no question is waiting with that call id")
        return {"call": call}
    def card_list(self) -> dict[str, Any]:
        return {"cards": self.cards.list()}

    def card_create(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "card": self.cards.create(request.get("title"), request.get("body"), request.get("by"))
        }

    def card_update(self, request: dict[str, Any]) -> dict[str, Any]:
        # Only the owner's screen sends "by": "owner"; agents will send their own id.
        changes = {k: request[k] for k in ("title", "body", "locked") if k in request}
        by = "owner" if request.get("by", "owner") == "owner" else "agent"
        return {"card": self.cards.update(request.get("id"), changes, by)}

    def card_list(self) -> dict[str, Any]:
        return {"cards": self.cards.list()}

    def card_create(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "card": self.cards.create(request.get("title"), request.get("body"), request.get("by"))
        }

    def card_update(self, request: dict[str, Any]) -> dict[str, Any]:
        # Only the owner's screen sends "by": "owner"; agents will send their own id.
        changes = {k: request[k] for k in ("title", "body", "locked") if k in request}
        by = "owner" if request.get("by", "owner") == "owner" else "agent"
        return {"card": self.cards.update(request.get("id"), changes, by)}

    # --- Journal, budgets and the network switch -------------------------------------------

    def note(self, kind: str, **fields: str | int | bool | None) -> None:
        """Write one line to the activity log. The log is best effort: it never fails a request."""
        try:
            journal.record(self.storage, kind, **fields)
        except OSError:
            logger.exception("Could not write the activity log")

    def journal_event(self, event: dict[str, Any]) -> None:
        """Turn the assistant's tool events into activity lines: outcomes and approvals."""
        if event.get("event") != "tool":
            return
        name, tier, status = event.get("name"), event.get("tier"), event.get("status")
        call = event.get("call")  # the card's id: ties each approval to the change it approved
        if tier in CONFIRM_TIERS and status in ("running", "declined"):
            self.note(
                "approval", tool=name, tier=tier, approved=status == "running", by="card", call=call
            )
        elif status in ("done", "failed", "refused"):
            self.note("tool", tool=name, tier=tier, status=status, call=call)

    def budget_overrun(self) -> budgets.Overrun | None:
        return self.ledger.first_overrun(
            {
                "app": (self.settings.budget, None),
                "assistant": (self.settings.assistant_budget, "assistant"),
            }
        )

    def budget(self) -> dict[str, Any]:
        """Each cap, and the tokens used so far in each window, for the app and the assistant."""
        now = datetime.now().astimezone()
        scopes = {
            "app": (self.settings.budget, None),
            "assistant": (self.settings.assistant_budget, "assistant"),
        }
        used = {
            scope: {w: self.ledger.used(w, now, agent) for w in CAP_WINDOWS}
            for scope, (_caps, agent) in scopes.items()
        }
        caps = {scope: asdict(caps) for scope, (caps, _agent) in scopes.items()}
        return {"caps": caps, "used": used, "allowance": self.allowance}

    def set_budget(self, request: dict[str, Any]) -> dict[str, Any]:
        caps = {}
        for scope in ("app", "assistant"):
            row = request.get(scope)
            if not isinstance(row, dict):
                raise ValueError(f'"{scope}" needs five_hour, daily, weekly and monthly caps')
            caps[scope] = Caps(**{w: _whole(row.get(w), w) for w in CAP_WINDOWS})
        save_budget(caps["app"], caps["assistant"], SETTINGS_PATH)
        self.settings = replace(
            self.settings, budget=caps["app"], assistant_budget=caps["assistant"]
        )
        self.note("setting", text="token budget caps changed")
        return self.budget()

    def budget_allow(self) -> dict[str, Any]:
        """Let the next request past a cap through, once."""
        self.allowance = True
        self.note("setting", text="one request allowed past a budget cap")
        return {"allowance": True}

    def network_state(self) -> dict[str, Any]:
        return {"mode": self.settings.network_mode, "modes": list(network.MODES)}

    def set_vault(self, request: dict[str, Any]) -> dict[str, Any]:
        # Opens the folder first, so a bad path is never saved.
        vault = request.get("vault")
        if not isinstance(vault, str) or not vault:
            raise ValueError('"set_vault" needs a "vault" folder path')
        folder = Path(vault).resolve()
        result = self.open(folder)
        save_vault(folder, self.settings_path)
        self.settings = replace(self.settings, vault=folder)
        self.note("setting", text=f"brain folder set to {folder.name}")
        return result

    def set_network(self, request: dict[str, Any]) -> dict[str, Any]:
        mode = request.get("mode")
        if not isinstance(mode, str):
            raise ValueError('"set_network" needs a "mode"')
        save_network_mode(mode, SETTINGS_PATH)  # raises ValueError on a bad mode
        network.set_mode(mode)
        self.settings = replace(self.settings, network_mode=mode)
        self.note("setting", text=f"network set to {mode}")
        return self.network_state()

    def activity(self, request: dict[str, Any]) -> dict[str, Any]:
        kind = request.get("kind")
        if kind is not None and kind not in journal.KINDS:
            raise ValueError(f"kind must be one of: {', '.join(journal.KINDS)}")
        limit = _whole(request.get("limit", 200), "limit")
        return {"rows": journal.read(self.storage, kind, min(limit, 500))}

    # --- Asks, memory, jobs, helpers, skills, share, keys ----------------------------------

    def asks_waiting(self) -> dict[str, Any]:
        return {"asks": [{"call": call, "question": q} for call, q in self.asks.waiting()]}

    def _memory_texts(self) -> dict[str, str]:
        """Every assistant memory note's text, keyed by vault path."""
        if self.indexer is None:
            raise ValueError("no vault is open")
        notes = {}
        for note in iter_notes(self.indexer.vault):
            text = (self.indexer.vault / note.path).read_text(encoding="utf-8", errors="replace")
            if memory_notes.is_memory(text):
                notes[note.path] = text
        return notes

    def memory_search(self, request: dict[str, Any]) -> dict[str, Any]:
        mode = request.get("mode", "text")
        query = request.get("query")
        if not isinstance(query, str):
            raise ValueError('"query" must be text')
        with self.lock:
            notes = self._memory_texts()
        if mode == "text":
            return {"mode": mode, "hits": memory_notes.search_text(notes, query)}
        if mode != "meaning":
            raise ValueError('"mode" is "text" or "meaning"')
        ranked = memory_notes.search_meaning(notes, query, self.embedder)
        return {"mode": mode, "hits": [{"path": p, "score": round(s, 3)} for p, s in ranked]}

    def memory_status(self) -> dict[str, Any]:
        return {**memory_notes.status(self.embedder), "max_bytes": self.settings.memory_max_bytes}

    def trim_memory(self) -> list[str]:
        """Move the oldest sections of long memory notes to archive notes. Runs on each open."""
        if self.indexer is None:
            return []
        changed: list[Path] = []
        for note in iter_notes(self.indexer.vault):
            path = self.indexer.vault / note.path
            archive = memory_notes.trim_memory_file(
                self.indexer.vault, path, self.settings.memory_max_bytes
            )
            if archive is not None:
                changed += [path, archive]
                self.note("setting", text=f"trimmed {note.path} into {archive.name}")
        if changed:
            with self.lock:
                self.indexer.apply_changes(changed)
        return [p.name for p in changed]

    def jobs(self) -> dict[str, Any]:
        return {"jobs": [asdict(j) for j in job_store.load(self.jobs_path)]}

    def set_job(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = request.get("id")
        if not isinstance(job_id, str) or not isinstance(request.get("enabled"), bool):
            raise ValueError('"set_job" needs an "id" and "enabled"')
        every = request.get("every_days")
        jobs = job_store.set_job(job_store.load(self.jobs_path), job_id, request["enabled"], every)
        job_store.save(self.jobs_path, jobs)
        return self.jobs()

    @property
    def jobs_path(self) -> Path:
        return self.storage / "jobs.json"

    def run_jobs(self, now: datetime | None = None) -> list[str]:
        """Run each enabled job that is due. Called on a timer by `serve`."""
        if self.indexer is None:
            return []
        runners = {"link_check": self._link_check}
        jobs, results = job_store.run_due(
            job_store.load(self.jobs_path), now or datetime.now().astimezone(), runners
        )
        job_store.save(self.jobs_path, jobs)
        for line in results:
            self.note("handoff", text=line)
        return results

    def _link_check(self) -> str:
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            store = self.indexer.store
            broken = sum(
                1
                for path in store.note_states()
                for _raw, target in store.outgoing(path)
                if target is None
            )
        return f"{broken} broken link(s)"

    def helpers_state(self) -> dict[str, Any]:
        return {"helpers": self.helpers.list(), "limit": 4}

    def start_helper(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt")
        if not isinstance(prompt, str):
            raise ValueError('"prompt" must be text')
        over = self.ledger.first_overrun({"app": (self.settings.budget, None)})
        if over is not None and not self.allowance:
            raise ValueError(f"the app {over.window} token cap is used; allow a request first")
        try:
            self.helpers.start(prompt)
        except HelperLimit as exc:
            raise ValueError(str(exc)) from exc
        return self.helpers_state()

    def _helper_run(self, prompt: str) -> str:
        router = build_router(self.settings, get_api_key())
        reply = asyncio.run(router.chat([{"role": "user", "content": prompt}], []))
        self.ledger.add("helper", reply.tokens)
        return reply.text

    def skills_state(self) -> dict[str, Any]:
        return {"skills": skills.list_skills(SKILLS_DIR)}

    def remove_skill(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("approve") is not True:
            raise ValueError("removing a skill needs the user's approval")
        name = request.get("name")
        skills.remove_skill(SKILLS_DIR, name)
        self.note("approval", tool="remove_skill", tier="act", approved=True, by="card")
        return self.skills_state()

    def install_skill(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("approve") is not True:
            raise ValueError("installing a skill needs the user's approval")
        name = skills.install_skill(SKILLS_DIR, request.get("path"))
        self.note(
            "approval", tool="install_skill", tier="write", approved=True, by="card", name=name
        )
        return self.skills_state()

    def open_skill_folder(self, request: dict[str, Any]) -> dict[str, Any]:
        skills.open_folder(SKILLS_DIR, request.get("name"), subprocess.Popen)
        self.note("tool", tool="open_skill_folder", tier="open", status="done")
        return self.skills_state()

    def agents_state(self) -> dict[str, Any]:
        return {"agents": added_agents.load(self.agents_path)}

    def save_agents(self, request: dict[str, Any]) -> dict[str, Any]:
        agents = request.get("agents")
        added_agents.save(self.agents_path, agents)
        return {"agents": agents}

    @property
    def agents_path(self) -> Path:
        return self.storage / "agents.json"

    def share_note(self, request: dict[str, Any]) -> dict[str, Any]:
        password = request.get("password")
        if not isinstance(password, str):
            raise ValueError('"password" must be text')
        minutes = _whole(request.get("minutes", share.DEFAULT_MINUTES), "minutes")
        share.request_link(password, minutes)  # always raises until a share host is set up
        return {}

    def webhooks_state(self) -> dict[str, Any]:
        return {"webhooks": webhooks.load(self.webhooks_path)}

    def save_webhook(self, request: dict[str, Any]) -> dict[str, Any]:
        hooks = webhooks.add(
            webhooks.load(self.webhooks_path), request.get("name"), request.get("kind")
        )
        webhooks.save(self.webhooks_path, hooks)
        return self.webhooks_state()

    def delete_webhook(self, request: dict[str, Any]) -> dict[str, Any]:
        hook_id = request.get("id")
        if not isinstance(hook_id, str):
            raise ValueError('"delete_webhook" needs an "id"')
        kept = webhooks.remove(webhooks.load(self.webhooks_path), hook_id)
        webhooks.save(self.webhooks_path, kept)
        return self.webhooks_state()

    def run_webhook(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("approve") is not True:
            raise ValueError("running a webhook needs the user's approval")
        hook = webhooks.find(webhooks.load(self.webhooks_path), request.get("id"))
        result = {"link_check": self._link_check}[hook["kind"]]()
        self.note("approval", tool="run_webhook", tier="act", approved=True, by="card")
        self.note("handoff", text=result)
        return {"result": result}

    @property
    def webhooks_path(self) -> Path:
        return self.storage / "webhooks.json"

    def keys(self) -> dict[str, Any]:
        rows = [{"provider": "claude", "label": "Claude (Anthropic)"}]
        rows += [
            {"provider": name, "label": preset.label}
            for name, preset in PRESETS.items()
            if preset.needs_key
        ]
        for row in rows:
            row["saved"] = get_key(row["provider"]) is not None
            row["hint"] = key_hint(row["provider"])
        return {"keys": rows}

    def _key_provider(self, request: dict[str, Any]) -> str:
        provider = request.get("provider")
        if provider != "claude" and not (provider in PRESETS and PRESETS[provider].needs_key):
            raise ValueError("no key is used by that provider")
        return str(provider)

    def save_key(self, request: dict[str, Any]) -> dict[str, Any]:
        provider = self._key_provider(request)
        key = request.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError('"save_key" needs a non-empty "key"')
        try:
            set_key(provider, key.strip())  # takes effect on the next request; no restart
        except KeyringError as error:
            raise ValueError(KEYCHAIN_MISSING) from error
        return self.keys()

    def clear_key(self, request: dict[str, Any]) -> dict[str, Any]:
        provider = self._key_provider(request)
        try:
            clear_key(provider)
        except KeyringError as error:
            raise ValueError(KEYCHAIN_MISSING) from error
        return self.keys()

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method")
        if method == "graph":
            return self.graph()
        if method == "open":
            vault = request.get("vault")
            if not isinstance(vault, str) or not vault:
                raise ValueError('"open" needs a "vault" folder path')
            return self.open(Path(vault))
        if method == "read":
            return self.read(request)
        if method == "account":
            return self.account()
        if method == "tasks":
            return self.tasks()
        if method == "inbox":
            return self.inbox()
        if method == "settings":
            return self.settings_view()
        if method == "memory":
            return self.memory_notes()
        if method == "sign_in":
            return self.sign_in(request)
        if method == "sign_out":
            return self.sign_out()
        if method == "remove_data":
            return self.remove_data()
        if method == "chat":
            return self.chat(request)
        if method == "confirm":
            return self.confirm(request)
        if method == "answer":
            return self.answer(request)
        if method == "tools":
            return self.tools()
        if method == "set_tools":
            return self.set_tools(request)
        if method == "cards":
            return self.card_list()
        if method == "card_create":
            return self.card_create(request)
        if method == "card_update":
            return self.card_update(request)
        if method == "stop":
            self.kill.trigger()
            return {"stopped": True}
        simple = {
            "network": self.network_state,
            "budget": self.budget,
            "budget_allow": self.budget_allow,
            "asks": self.asks_waiting,
            "memory_status": self.memory_status,
            "jobs": self.jobs,
            "helpers": self.helpers_state,
            "skills": self.skills_state,
            "keys": self.keys,
            "webhooks": self.webhooks_state,
            "agents": self.agents_state,
        }
        if method in simple:
            return simple[method]()
        extra = {
            "set_network": self.set_network,
            "set_vault": self.set_vault,
            "set_budget": self.set_budget,
            "activity": self.activity,
            "memory_search": self.memory_search,
            "set_job": self.set_job,
            "start_helper": self.start_helper,
            "remove_skill": self.remove_skill,
            "install_skill": self.install_skill,
            "open_skill_folder": self.open_skill_folder,
            "share": self.share_note,
            "save_agents": self.save_agents,
            "save_key": self.save_key,
            "clear_key": self.clear_key,
            "save_webhook": self.save_webhook,
            "delete_webhook": self.delete_webhook,
            "run_webhook": self.run_webhook,
        }
        if method in extra:
            return extra[method](request)
        raise ValueError(f"unknown method: {method!r}")

    def close(self) -> None:
        with self.lock:
            if self.indexer is not None:
                self.indexer.store.close()
                self.indexer = None


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'"{name}" must be a whole number, 0 or more')
    return value


def handle(session: Session, line: str) -> dict[str, Any]:
    """Answer one request line. Never raises: every failure becomes an error answer."""
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return {"id": None, "error": f"invalid JSON: {exc.msg}"}
    if not isinstance(request, dict):
        return {"id": None, "error": "request must be a JSON object"}
    request_id = request.get("id")
    try:
        return {"id": request_id, "result": session.dispatch(request)}
    except Exception as exc:
        logger.exception("Request %r failed", request_id)
        session.note("error", method=str(request.get("method")), text=str(exc)[:300])
        return {"id": request_id, "error": str(exc)}


class Writer:
    """Writes one JSON line at a time, from any thread."""

    def __init__(self, out: TextIO) -> None:
        self._out = out
        self._lock = threading.Lock()

    def __call__(self, message: dict[str, Any]) -> None:
        with self._lock:
            print(json.dumps(message), file=self._out, flush=True)


def _method(line: str) -> object:
    try:
        request = json.loads(line)
    except ValueError:
        return None
    return request.get("method") if isinstance(request, dict) else None


def _answer(session: Session, line: str, send: Writer) -> None:
    send(handle(session, line))


def _schedule(session: Session, stop: threading.Event) -> None:
    """Runs the due notes jobs every minute until `serve` stops."""
    while not stop.wait(SCHEDULE_SECONDS):
        try:
            session.run_jobs()
        except Exception:
            logger.exception("Scheduled jobs failed")


def serve(
    storage: Path,
    vault: Path | None = None,
    lines: TextIO = sys.stdin,
    out: TextIO = sys.stdout,
    settings: Settings | None = None,
    settings_path: Path = SETTINGS_PATH,
) -> int:
    send = Writer(out)
    session = Session(storage, settings, emit=send, settings_path=settings_path)
    chats: list[threading.Thread] = []
    stop_schedule = threading.Event()
    threading.Thread(target=_schedule, args=(session, stop_schedule), daemon=True).start()
    try:
        send({"status": "ready", "version": __version__})
        if vault is not None:
            try:
                session.open(vault)
            except Exception:
                logger.exception("Could not open vault %s", vault)
        for line in lines:
            if not line.strip():
                continue
            if _method(line) == "chat":
                # A chat runs beside the other requests, so stop and confirm still get through.
                chats = [t for t in chats if t.is_alive()]
                worker = threading.Thread(target=_answer, args=(session, line, send), daemon=True)
                chats.append(worker)
                worker.start()
            else:
                send(handle(session, line))
    except KeyboardInterrupt:
        logger.info("Sidecar interrupted; shutting down")
    finally:
        stop_schedule.set()
        session.kill.trigger()
        for worker in chats:
            worker.join(timeout=5)
        session.close()
    return 0


def index(vault: Path, storage: Path) -> int:
    indexer = open_index(vault, storage)
    try:
        stats = indexer.full_sync()
        counts = indexer.store.counts()
    finally:
        indexer.store.close()
    status = {"status": "indexed", "index": str(indexer.store.db_path), **counts}
    status.update({f"{k}_files": getattr(stats, k) for k in stats.__slots__})
    print(json.dumps(status), flush=True)
    return 0


async def _watch(vault: Path, storage: Path) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        # Windows event loops cannot catch these; stdin EOF and Ctrl+C still stop the watch there.
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    def wait_for_stdin_eof() -> None:
        for _ in sys.stdin:
            pass
        loop.call_soon_threadsafe(stop.set)

    threading.Thread(target=wait_for_stdin_eof, name="stdin-eof", daemon=True).start()

    indexer = open_index(vault, storage)
    watcher = VaultWatcher(indexer)
    try:
        task = asyncio.create_task(watcher.run(stop))
        ready = asyncio.create_task(watcher.ready.wait())
        await asyncio.wait({task, ready}, return_when=asyncio.FIRST_COMPLETED)
        if watcher.ready.is_set():
            status = {"status": "watching", "index": str(indexer.store.db_path)}
            print(json.dumps({**status, **indexer.store.counts()}), flush=True)
        ready.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ready
        await task
    finally:
        indexer.store.close()


def watch(vault: Path, storage: Path) -> int:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_watch(vault, storage))
    return 0


def manage_key(action: str) -> int:
    try:
        if action == "set":
            set_api_key(getpass.getpass("Claude API key: ").strip())
            print("Saved the Claude API key in the OS keychain.")
        elif action == "clear":
            clear_api_key()
            print("Removed the Claude API key from the OS keychain.")
        else:
            print("Claude API key: " + ("set" if get_api_key() else "not set"))
    except KeyringError as error:
        # Linux needs a running Secret Service (gnome-keyring or KWallet).
        print(f"The OS keychain is not available: {error}", file=sys.stderr)
        return 1
    return 0


def _vault_dir(value: str) -> Path:
    path = Path(value)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"vault folder not found: {value}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve_cmd = sub.add_parser("serve", help="Answer JSON requests on stdin until it closes")
    serve_cmd.add_argument(
        "vault", nargs="?", type=_vault_dir, help="vault to open at start (default: config)"
    )
    serve_cmd.add_argument(
        "--storage", type=Path, default=DEFAULT_STORAGE, help="folder for the index"
    )
    serve_cmd.add_argument(
        "--settings", type=Path, default=SETTINGS_PATH, help="settings file (default: config/)"
    )
    for name, help_text in (
        ("index", "Build or refresh a vault's index, then exit"),
        ("watch", "Index a vault, then keep the index current until stopped"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("vault", type=_vault_dir, help="folder of Markdown notes")
        cmd.add_argument(
            "--storage",
            type=Path,
            default=DEFAULT_STORAGE,
            help="folder for the index (default: storage/ in the project)",
        )
    key_cmd = sub.add_parser("key", help="Manage the Claude API key in the OS keychain")
    key_cmd.add_argument("action", choices=["set", "status", "clear"])
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if args.command == "serve":
        settings = load_settings(args.settings)
        return serve(
            args.storage,
            args.vault or settings.vault,
            settings=settings,
            settings_path=args.settings,
        )
    if args.command == "key":
        return manage_key(args.action)
    if args.command == "index":
        return index(args.vault, args.storage)
    if args.command == "watch":
        return watch(args.vault, args.storage)
    return 1


if __name__ == "__main__":
    sys.exit(main())
