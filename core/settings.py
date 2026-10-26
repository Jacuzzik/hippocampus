"""Reads config/settings.toml. It holds no secrets: API keys live in the OS keychain."""

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ai.providers.openai_compat import PRESETS

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.toml"


@dataclass(frozen=True)
class Settings:
    # Version of this file's layout. Only 1 exists; a later release migrates older files.
    settings_version: int = 1
    vault: Path | None = None
    # "claude" or a preset from ai/providers/openai_compat.py. Ollama is the fallback.
    provider: str = "claude"
    # Model for the chosen preset; empty means its first model. Claude uses claude_model.
    provider_model: str = ""
    claude_model: str = "claude-sonnet-5-5"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b"
    # Tool calls the assistant may make in one request before it pauses for the user to continue.
    max_tool_calls: int = 20
    # Tools the assistant may use, by name. None means every tool.
    allowed_tools: tuple[str, ...] | None = None


_TOOL_NAME = re.compile(r"[a-z][a-z0-9_]*")


def _tool_limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("ai.max_tool_calls must be a whole number of 1 or more")
    return value


def _allowed_tools(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(
        isinstance(name, str) and _TOOL_NAME.fullmatch(name) for name in value
    ):
        raise ValueError("ai.allowed_tools must be a list of tool names")
    return tuple(value)


def _provider(value: object) -> str:
    if value != "claude" and value not in PRESETS:
        raise ValueError(f"ai.provider must be claude or one of: {', '.join(PRESETS)}")
    return str(value)


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Read the settings file. A missing file gives the defaults; a bad one is an error."""
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if data.get("settings_version", Settings.settings_version) != Settings.settings_version:
        raise ValueError(f"settings_version must be {Settings.settings_version}")
    # HIPPOCAMPUS_VAULT wins over the file, so a launcher can pick the vault without editing it.
    vault = os.environ.get("HIPPOCAMPUS_VAULT") or data.get("vault", {}).get("path")
    ai = data.get("ai", {})
    defaults = Settings()
    return Settings(
        vault=(path.parent.parent / vault).resolve() if vault else None,
        provider=_provider(ai.get("provider", defaults.provider)),
        provider_model=str(ai.get("provider_model", defaults.provider_model)),
        claude_model=str(ai.get("claude_model", defaults.claude_model)),
        ollama_host=str(ai.get("ollama_host", defaults.ollama_host)),
        ollama_model=str(ai.get("ollama_model", defaults.ollama_model)),
        max_tool_calls=_tool_limit(ai.get("max_tool_calls", defaults.max_tool_calls)),
        allowed_tools=_allowed_tools(ai.get("allowed_tools")),
    )


def save_allowed_tools(names: tuple[str, ...] | None, path: Path = SETTINGS_PATH) -> None:
    """Write `ai.allowed_tools` to the settings file, keeping the rest. None removes the key."""
    if names is not None and not all(_TOOL_NAME.fullmatch(name) for name in names):
        raise ValueError("tool names are lowercase words with underscores")
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = [line for line in text.splitlines() if not re.match(r"\s*allowed_tools\s*=", line)]
    if names is not None:
        entry = "allowed_tools = [" + ", ".join(f'"{name}"' for name in names) + "]"
        headers = [line.strip() for line in lines]
        if "[ai]" in headers:
            lines.insert(headers.index("[ai]") + 1, entry)
        else:
            lines += ["", "[ai]", entry]
    new = "\n".join(lines) + "\n"
    tomllib.loads(new)  # refuse to write a file that no longer parses
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(new, encoding="utf-8")
    tmp.replace(path)
