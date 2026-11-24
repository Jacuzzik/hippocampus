"""Plugins (D.07): packs that add several skills, commands, helpers and tool servers in one install.

A plugin is a Claude Code plugin: a folder (or a .zip of one) with `.claude-plugin/plugin.json`
and any of `skills/`, `commands/`, `agents/` and `.mcp.json`. An installed plugin is unpacked into
storage/plugins/<name>, and every agent on Claude Code starts with each switched-on plugin
(`--plugin-dir`). Nothing is downloaded: the user adds the file.
"""

import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from core import safe_write

FILE_MAX = 20_000_000
UNPACKED_MAX = 80_000_000
FILES_MAX = 2000
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
STATE = "plugins.json"


def _manifest(folder: Path) -> dict[str, Any]:
    path = folder / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(
            "This is not a plugin: it has no readable .claude-plugin/plugin.json."
        ) from error
    if not isinstance(data, dict) or not NAME.match(str(data.get("name", ""))):
        raise ValueError("The plugin's name must be lower-case letters, digits and -.")
    return data


def _count(folder: Path, part: str, pattern: str) -> int:
    return len(list((folder / part).glob(pattern))) if (folder / part).is_dir() else 0


def describe(folder: Path, enabled: bool) -> dict[str, Any]:
    data = _manifest(folder)
    servers: list[str] = []
    try:
        found = (
            json.loads((folder / ".mcp.json").read_text(encoding="utf-8")).get("mcpServers") or {}
        )
        servers = sorted(found) if isinstance(found, dict) else []
    except (OSError, ValueError, AttributeError):
        pass
    return {
        "name": data["name"],
        "version": str(data.get("version", "")),
        "description": str(data.get("description", ""))[:300],
        "skills": _count(folder, "skills", "*/SKILL.md"),
        "commands": _count(folder, "commands", "*.md"),
        "helpers": _count(folder, "agents", "*.md"),
        "servers": servers,
        "enabled": enabled,
    }


class Plugins:
    def __init__(self, storage: Path) -> None:
        self.root = storage / "plugins"
        self.state_path = storage / STATE

    def _off(self) -> set[str]:
        try:
            return set(json.loads(self.state_path.read_text(encoding="utf-8")).get("off") or [])
        except (OSError, ValueError, AttributeError):
            return set()

    def rows(self) -> list[dict[str, Any]]:
        off = self._off()
        rows = []
        for folder in sorted(self.root.iterdir()) if self.root.is_dir() else []:
            try:
                rows.append(describe(folder, folder.name not in off))
            except ValueError:
                continue
        return rows

    def enabled_dirs(self) -> list[str]:
        off = self._off()
        return [str(self.root / row["name"]) for row in self.rows() if row["name"] not in off]

    def install(self, name: str, data: bytes) -> list[dict[str, Any]]:
        if len(data) > FILE_MAX:
            raise ValueError("The plugin file is larger than 20 MB.")
        if not name.lower().endswith(".zip"):
            raise ValueError("Add the plugin as a .zip file.")
        try:
            pack = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as error:
            raise ValueError("The file is not a readable .zip.") from error
        entries = [e for e in pack.infolist() if not e.is_dir()]
        if len(entries) > FILES_MAX or sum(e.file_size for e in entries) > UNPACKED_MAX:
            raise ValueError("The plugin is too large once unpacked.")
        manifests = [
            e.filename for e in entries if e.filename.endswith(".claude-plugin/plugin.json")
        ]
        if not manifests:
            raise ValueError("This is not a plugin: it has no .claude-plugin/plugin.json.")
        prefix = min(manifests, key=len)[: -len(".claude-plugin/plugin.json")]
        staging = self.root / ".incoming"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        try:
            for entry in entries:
                if not entry.filename.startswith(prefix):
                    continue
                rel = Path(entry.filename[len(prefix) :])
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError("The plugin has a file path that leaves its folder.")
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("The plugin holds a link, which is not taken.")
                target = staging / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(pack.read(entry))
            plugin = _manifest(staging)["name"]
            final = self.root / plugin
            shutil.rmtree(final, ignore_errors=True)
            staging.rename(final)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return self.rows()

    def set_enabled(self, name: str, on: bool) -> list[dict[str, Any]]:
        if not any(row["name"] == name for row in self.rows()):
            raise ValueError("No installed plugin has that name.")
        off = self._off()
        (off.discard if on else off.add)(name)
        safe_write.write_text(self.state_path, json.dumps({"off": sorted(off)}))
        return self.rows()

    def remove(self, name: str) -> list[dict[str, Any]]:
        if not NAME.match(name) or not (self.root / name).is_dir():
            raise ValueError("No installed plugin has that name.")
        shutil.rmtree(self.root / name)
        return self.rows()
