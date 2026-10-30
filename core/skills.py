"""Installed skills: folders under skills/ that hold a SKILL.md file."""

import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
FILE_MANAGER = {"darwin": "open", "win32": "explorer"}.get(sys.platform, "xdg-open")


def list_skills(root: Path) -> list[dict[str, str]]:
    if not root.is_dir():
        return []
    skills = []
    for folder in sorted(root.iterdir()):
        manifest = folder / "SKILL.md"
        if not folder.is_dir() or not manifest.is_file():
            continue
        skills.append(
            {
                "name": folder.name,
                "description": _description(manifest.read_text(encoding="utf-8")),
                "path": str(folder.resolve()),
            }
        )
    return skills


def _description(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    return ""


def skill_folder(root: Path, name: object) -> Path:
    """The folder of one installed skill. Refuses any name that could leave the skills folder."""
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("skill names are lowercase letters, digits and hyphens")
    folder = (root / name).resolve()
    if folder.parent != root.resolve() or not (folder / "SKILL.md").is_file():
        raise ValueError(f"no installed skill named {name}")
    return folder


def remove_skill(root: Path, name: object) -> None:
    shutil.rmtree(skill_folder(root, name))


def install_skill(root: Path, source: object) -> str:
    """Copy a skill folder (one holding SKILL.md) into the skills folder. Returns its name."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("give the path of a skill folder")
    folder = Path(source.strip()).expanduser().resolve()
    if not (folder / "SKILL.md").is_file():
        raise ValueError(f"{folder} has no SKILL.md file")
    if not NAME.fullmatch(folder.name):
        raise ValueError("skill names are lowercase letters, digits and hyphens")
    if (root / folder.name).exists():
        raise ValueError(f"a skill named {folder.name} is already installed")
    shutil.copytree(folder, root / folder.name)
    return folder.name


def open_folder(root: Path, name: object, launch: Callable[[list[str]], object]) -> None:
    # shortcut: one fixed file-manager command per OS, no shell; upgrade if a platform needs more.
    launch([FILE_MANAGER, str(skill_folder(root, name))])
