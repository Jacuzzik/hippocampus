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
import shutil
import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, TextIO

from keyring.errors import KeyringError

from ai.agent import Agent, AgentPaused
from ai.keys import clear_api_key, get_api_key, set_api_key
from ai.router import build_router, model_name
from core import __version__
from core.cards import CardStore
from core.settings import SETTINGS_PATH, Settings, load_settings, save_allowed_tools
from core.vault import Indexer, open_index
from core.vault.watcher import VaultWatcher
from tools.gate import AskQueue, ConfirmGate, KillSwitch, Stopped
from tools.vault_tools import vault_tools

logger = logging.getLogger("hippocampus.core")

DEFAULT_STORAGE = Path(__file__).resolve().parent.parent / "storage"
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
        self, storage: Path, settings: Settings | None = None, emit: Emit | None = None
    ) -> None:
        self.storage = storage
        self.settings = settings if settings is not None else load_settings(SETTINGS_PATH)
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

    def open(self, vault: Path) -> dict[str, Any]:
        if not vault.is_dir():
            raise ValueError(f"vault folder not found: {vault}")
        with self.lock:
            self.close()
            self.indexer = open_index(vault, self.storage)
            stats = self.indexer.full_sync()
            status = {f"{k}_files": getattr(stats, k) for k in stats.__slots__}
            return {"vault": str(vault.resolve()), **self.indexer.store.counts(), **status}

    def account(self) -> dict[str, Any]:
        # Only whether a key is saved and the model name; the key itself never leaves the keychain.
        api_key = get_api_key()
        return {"claude": api_key is not None, "model": model_name(self.settings, api_key)}

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
        messages, self.paused = self.paused, None
        if request.get("continue") is True and messages is None:
            raise ValueError("nothing is paused to continue")
        if request.get("continue") is not True:
            messages = None
        self.kill.reset()  # a stop only ends the work that was running when it was sent
        tools = vault_tools(self.indexer, self.lock) if self.indexer is not None else {}
        router = build_router(self.settings, get_api_key())

        def emit(event: dict[str, Any]) -> None:
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
            return {"reply": "", "stopped": False, "limit": paused.limit}
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
        raise ValueError(f"unknown method: {method!r}")

    def close(self) -> None:
        with self.lock:
            if self.indexer is not None:
                self.indexer.store.close()
                self.indexer = None


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


def serve(
    storage: Path,
    vault: Path | None = None,
    lines: TextIO = sys.stdin,
    out: TextIO = sys.stdout,
    settings: Settings | None = None,
) -> int:
    send = Writer(out)
    session = Session(storage, settings, emit=send)
    chats: list[threading.Thread] = []
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
        return serve(args.storage, args.vault or settings.vault, settings=settings)
    if args.command == "key":
        return manage_key(args.action)
    if args.command == "index":
        return index(args.vault, args.storage)
    if args.command == "watch":
        return watch(args.vault, args.storage)
    return 1


if __name__ == "__main__":
    sys.exit(main())
