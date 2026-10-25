"""Sidecar entry point.

`serve` runs the JSON-lines bridge the Tauri shell talks to. It prints a ready line,
then reads one JSON request per line on stdin and answers each with one line on stdout.
Requests: {"id": ..., "method": "graph"} and {"id": ..., "method": "open", "vault": "<folder>"}.
Answers: {"id": ..., "result": ...} or {"id": ..., "error": "<message>"}. A bad line gets an
error answer and the loop keeps going. It runs until stdin closes. No network listener.

`index` and `watch` build and maintain a vault's SQLite index. Each prints one
JSON status line on stdout and logs to stderr. `watch` runs until Ctrl+C,
SIGTERM or stdin closes.
"""

import argparse
import asyncio
import contextlib
import json
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Any, TextIO

from core import __version__
from core.vault import Indexer, open_index
from core.vault.watcher import VaultWatcher

logger = logging.getLogger("hippocampus.core")

DEFAULT_STORAGE = Path(__file__).resolve().parent.parent / "storage"


class Session:
    """The vault the serve loop has open, and the requests it answers."""

    def __init__(self, storage: Path) -> None:
        self.storage = storage
        self.indexer: Indexer | None = None

    def open(self, vault: Path) -> dict[str, Any]:
        if not vault.is_dir():
            raise ValueError(f"vault folder not found: {vault}")
        self.close()
        self.indexer = open_index(vault, self.storage)
        stats = self.indexer.full_sync()
        status = {f"{k}_files": getattr(stats, k) for k in stats.__slots__}
        return {"vault": str(vault.resolve()), **self.indexer.store.counts(), **status}

    def graph(self) -> dict[str, Any]:
        if self.indexer is None:
            raise ValueError("no vault is open")
        return self.indexer.store.graph()

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method")
        if method == "graph":
            return self.graph()
        if method == "open":
            vault = request.get("vault")
            if not isinstance(vault, str) or not vault:
                raise ValueError('"open" needs a "vault" folder path')
            return self.open(Path(vault))
        raise ValueError(f"unknown method: {method!r}")

    def close(self) -> None:
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


def serve(storage: Path, vault: Path | None = None, lines: TextIO = sys.stdin) -> int:
    session = Session(storage)
    try:
        if vault is not None:
            session.open(vault)
        print(json.dumps({"status": "ready", "version": __version__}), flush=True)
        for line in lines:
            if line.strip():
                print(json.dumps(handle(session, line)), flush=True)
    except KeyboardInterrupt:
        logger.info("Sidecar interrupted; shutting down")
    finally:
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
    asyncio.run(_watch(vault, storage))
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
    serve_cmd.add_argument("vault", nargs="?", type=_vault_dir, help="vault to open at start")
    serve_cmd.add_argument(
        "--storage", type=Path, default=DEFAULT_STORAGE, help="folder for the index"
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
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if args.command == "serve":
        return serve(args.storage, args.vault)
    if args.command == "index":
        return index(args.vault, args.storage)
    if args.command == "watch":
        return watch(args.vault, args.storage)
    return 1


if __name__ == "__main__":
    sys.exit(main())
