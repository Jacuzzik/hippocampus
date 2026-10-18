"""Sidecar entry point.

D1 stub: no network listener. `serve` announces readiness as one JSON line on
stdout and runs until stdin closes, which is how the Tauri shell will stop it.
"""

import argparse
import json
import logging
import sys

from core import __version__

logger = logging.getLogger("hippocampus.core")


def serve() -> int:
    print(json.dumps({"status": "ready", "version": __version__}), flush=True)
    try:
        for _ in sys.stdin:
            pass
    except KeyboardInterrupt:
        logger.info("Sidecar interrupted; shutting down")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run the sidecar until stdin closes")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if args.command == "serve":
        return serve()
    return 1


if __name__ == "__main__":
    sys.exit(main())
