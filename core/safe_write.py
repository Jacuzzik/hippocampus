"""Write a file so that a crash or a power cut never leaves half of it on disk."""

import os
from pathlib import Path


def write_text(path: Path, text: str) -> None:
    """The whole text goes to a file beside the target, then takes its place in one step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as file:
        file.write(text)
        file.flush()
        os.fsync(file.fileno())
    temp.replace(path)
