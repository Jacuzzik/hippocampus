"""Installed skills: folders under skills/ that hold a SKILL.md file."""

import re
import shutil
from pathlib import Path

NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


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
