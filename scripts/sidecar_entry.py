"""PyInstaller entry point: the packaged sidecar runs `core` with the same arguments as `python -m core`."""

import sys

from core.__main__ import main

sys.exit(main())
