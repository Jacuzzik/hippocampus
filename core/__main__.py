"""Sidecar entry point.

`serve` is the D1 stub: no network listener. It announces readiness as one JSON
line on stdout and runs until stdin closes, which is how the Tauri shell will
stop it.

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

from core import __version__
from core.vault import open_index
from core.vault.watcher import VaultWatcher

logger = logging.getLogger("hippocampus.core")

DEFAULT_STORAGE = Path(__file__).resolve().parent.parent / "storage"


def serve() -> int:
    print(json.dumps({"status": "ready", "version": __version__}), flush=True)
    try:
        for _ in sys.stdin:
            pass
    except KeyboardInterrupt:
        logger.info("Sidecar interrupted; shutting down")
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
    sub.add_parser("serve", help="Run the sidecar until stdin closes")
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
        return serve()
    if args.command == "index":
        return index(args.vault, args.storage)
    if args.command == "watch":
        return watch(args.vault, args.storage)
    return 1


if __name__ == "__main__":
    sys.exit(main())
