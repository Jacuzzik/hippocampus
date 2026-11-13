"""Sidecar entry point.

`serve` runs the JSON-lines bridge the Tauri shell talks to. It prints a ready line,
then reads one JSON request per line on stdin and answers each with one line on stdout.
Requests: {"id": ..., "method": "graph"}, {"id": ..., "method": "open", "vault": "<folder>"} and
{"id": ..., "method": "read", "path": "<note id>"} (answers {"id": <note id>, "text": ...}).
{"method": "account"} answers {"claude": true|false}; {"method": "sign_in", "key": "<key>"} saves
the Claude key in the keychain and {"method": "sign_out"} removes it. Neither ever returns the key.
{"method": "remove_data"} deletes the index cache and the key; the vault is never touched.
Answers: {"id": ..., "result": ...} or {"id": ..., "error": "<message>", "code": "<kind>"}, with a
"hint" (the next step) when one is known. A bad line gets an
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
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from keyring.errors import KeyringError

from ai import chat_history, cli_sessions, network
from ai.agent import Agent, AgentPaused
from ai.keys import clear_api_key, clear_key, get_api_key, get_key, key_hint, set_api_key, set_key
from ai.providers.openai_compat import PRESETS
from ai.router import build_router, model_name
from core import (
    __version__,
    added_agents,
    app_log,
    crash_log,
    inbox,
    migrate,
    skills,
)
from core import activity as journal
from core import budget as budgets
from core import memory as memory_notes
from core.cards import CardStore
from core.helpers import Helpers
from core.session_agents import AgentsPart
from core.session_budget import BudgetPart
from core.session_connectors import ConnectorsPart
from core.session_dispatch import DispatchPart
from core.session_hive import HivePart
from core.session_jobs import JobsPart
from core.session_memory import MemoryPart
from core.session_notes import NotesPart
from core.session_records import RecordsPart
from core.session_settings import SettingsPart
from core.session_shared import (
    DEFAULT_STORAGE,
    DEFAULT_TASKS_FILE,
    KEYCHAIN_MISSING,
    SCHEDULE_SECONDS,
    SKILLS_DIR,
    Emit,
    _whole,
    logger,
)
from core.session_terminal import TerminalPart
from core.settings import (
    CAP_WINDOWS,
    HIVE_DIR,
    SETTINGS_PATH,
    Caps,
    Settings,
    load_settings,
    save_allowed_tools,
    save_budget,
    save_network_mode,
    save_vault,
)
from core.system_stats import SystemStats
from core.terminal import Terminals
from core.vault import Indexer, open_index
from core.vault.changes import ChangeFlag
from core.vault.watcher import VaultWatcher
from tools.agent_tools import agent_tools
from tools.gate import AskQueue, ConfirmGate, KillSwitch, Stopped
from tools.registry import CONFIRM_TIERS
from tools.vault_tools import vault_tools


class Session(
    JobsPart,
    HivePart,
    RecordsPart,
    TerminalPart,
    NotesPart,
    MemoryPart,
    AgentsPart,
    SettingsPart,
    BudgetPart,
    DispatchPart,
    ConnectorsPart,
):
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
        # Bring an older data folder up to this version (after a backup); refuse one from a newer app.
        migrate.migrate(storage)
        # The sessions and chat history live in the app's storage folder, which survives restarts.
        cli_sessions.FILE = storage / "claude_sessions.json"
        chat_history.FILE = storage / "chat_history.json"
        self.system = SystemStats()
        self.settings_path = settings_path
        self.settings = settings if settings is not None else load_settings(settings_path)
        self.emit: Emit = emit or (lambda _event: None)
        self.terminals = Terminals(lambda event: self.emit(event), storage / "terminals")
        # Daily compaction: the day it last ran, and agents that were sent the save prompt (name -> time sent).
        # Starting after 03:00 counts today's save as done, so the first save is the next 03:00, not right at startup.
        now = datetime.now()
        self.compact_day: str | None = now.date().isoformat() if now.hour >= 3 else None
        self.compact_waiting: dict[str, float] = {}
        # Agents whose start-up inbox has not yet been typed into their terminal (agent -> inbox file path).
        self.inbox_pending: dict[str, str] = {}
        self.boot = uuid.uuid4().hex
        # The version and hash of the briefing each agent last started with, for its card.
        self.briefing_stamps: dict[str, dict[str, Any]] = {}
        # Holds messages between two agents that keep answering each other, and remembers who was told.
        self.loop_guard = inbox.LoopGuard()
        self.loop_alerts: dict[tuple[str, str], float] = {}
        self.last_archive = 0.0
        # Every agent gets its start-up inbox file when the app starts, whether or not its terminal is open.
        self._write_all_inboxes()
        threading.Thread(target=self._deliver_loop, daemon=True).start()
        self.indexer: Indexer | None = None
        # Raised when the vault changes on disk, so the graph syncs only when there is something to read.
        self.vault_changes: ChangeFlag | None = None
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

    def account(self) -> dict[str, Any]:
        # Only whether a key is saved and the model name; the key itself never leaves the keychain.
        api_key = get_api_key()
        return {
            "claude": api_key is not None,
            "model": model_name(self.settings, api_key),
            "provider": self.settings.provider,
        }

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
        """Every message between this app's agents, with its state. Queued ones first, then newest first."""
        rows = inbox.all_messages(self.hive_path)
        # Stable sort: queued rows float above the rest before the cap, or an old waiting message vanishes.
        rows.sort(key=lambda row: row["state"] != "queued")
        return {"messages": rows[:200], "acts": list(inbox.ACTS)}

    def inbox_search(self, request: dict[str, Any]) -> dict[str, Any]:
        query = request.get("query")
        if not isinstance(query, str):
            raise ValueError('"query" must be text')
        return {"messages": inbox.search(self.hive_path, query)[:200]}

    def inbox_thread(self, request: dict[str, Any]) -> dict[str, Any]:
        """One conversation, oldest first, and the same thing as Markdown for export."""
        thread = request.get("thread")
        if not isinstance(thread, str) or not thread:
            raise ValueError('"thread" must be a thread id')
        return {
            "messages": inbox.thread(self.hive_path, thread),
            "markdown": inbox.export_thread(self.hive_path, thread),
        }

    def _agent_ids(self) -> set[str]:
        """Every agent that can receive a message: the main agent and each added one."""
        return {"hippoherman"} | {
            str(a["id"]) for a in added_agents.load(self.agents_path) if a.get("id")
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

    # The graph's right-click actions. The app asks for each one after the user picks it; deletes are confirmed there.

    def chat(self, request: dict[str, Any]) -> dict[str, Any]:
        text = request.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError('"chat" needs a non-empty "text"')
        chat_id = request.get("chat")  # the UI names each chat so it can match its events
        over = None if self.allowance else self.budget_overrun()
        if over is not None:
            self.note("budget", text=f"paused: {over.scope} {over.window} cap reached")
            return {"reply": "", "stopped": False, "budget": over.as_dict()}
        if request.get("continue") is True and self.paused is None:
            raise ValueError("nothing is paused to continue")
        self.allowance = False
        messages, self.paused = self.paused, None
        agent_name = (
            request.get("agent") if isinstance(request.get("agent"), str) else "hippoherman"
        )
        if request.get("continue") is not True:
            # The saved chat turns give the model the conversation so far (Claude's session keeps its own).
            messages = chat_history.model_turns(agent_name)
        else:
            self.note("handoff", text="continued a request paused at the tool-call limit")
        self.kill.reset()  # a stop only ends the work that was running when it was sent
        tools = vault_tools(self.indexer, self.lock) if self.indexer is not None else {}
        tools.update(agent_tools(self.hive_path, self.agents_path))
        router = build_router(self.settings, get_api_key(), agent_name)

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

    @property
    def hive_path(self) -> Path:
        # One folder per agent, with an inbox and an outbox for task messages. Kept outside the app folder.
        return HIVE_DIR

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

    def close(self) -> None:
        with self.lock:
            if self.vault_changes is not None:
                self.vault_changes.stop()
                self.vault_changes = None
            if self.indexer is not None:
                self.indexer.store.close()
                self.indexer = None


def record_thread_errors(storage: Path) -> Callable[[], None]:
    """Writes any error a background thread did not handle to the crash log. Returns the undo."""
    previous = threading.excepthook

    def hook(args: threading.ExceptHookArgs) -> None:
        try:
            name = args.thread.name if args.thread else "?"
            crash_log.record(
                storage, f"backend thread {name}", f"{args.exc_type.__name__}: {args.exc_value}"
            )
        except Exception:  # the log must never take the sidecar down
            logger.exception("Could not write the crash record")
        previous(args)

    threading.excepthook = hook

    def restore() -> None:
        threading.excepthook = previous

    return restore


# What to do next, by the kind of failure. The window shows it after the message.
ERROR_HINTS = {
    "NotSetUp": "Open Settings, then Doctor, to see what is missing.",
    "KeyringError": "The system keychain did not answer. Check that a keyring service is running.",
    "NetworkBlocked": "Network use is switched off. Turn it on in Settings to use this.",
    "TimeoutExpired": "The program took too long to answer. Try again.",
}


def error_answer(request_id: object, exc: Exception) -> dict[str, Any]:
    """One shape for every failure: the message, a stable code, and the next step when one is known."""
    names = [kind.__name__ for kind in type(exc).__mro__]
    answer: dict[str, Any] = {"id": request_id, "error": str(exc), "code": names[0]}
    hint = next((ERROR_HINTS[name] for name in names if name in ERROR_HINTS), None)
    if hint:
        answer["hint"] = hint
    return answer


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
        return error_answer(request_id, exc)


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
    restore_hook = record_thread_errors(storage)
    close_log = app_log.attach(storage)
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
        restore_hook()
        close_log()
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
            help="folder for the index (default: data/storage/ in the project)",
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
