"""Reads config/settings.toml. It holds no secrets: API keys live in the OS keychain."""

import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ai.network import MODES as NETWORK_MODES
from ai.providers.openai_compat import PRESETS

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.toml"


# Token cap windows, shortest first. five_hour is a rolling 5 hours back from now.
CAP_WINDOWS = ("five_hour", "daily", "weekly", "monthly")


@dataclass(frozen=True)
class Caps:
    """Token caps for one scope. 0 means no cap for that window."""

    five_hour: int = 0
    daily: int = 0
    weekly: int = 0
    monthly: int = 0


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
    # Outbound switch: off, listen, converse or open. Converse is the default.
    network_mode: str = "converse"
    # Token caps for the whole app, and for the assistant.
    budget: Caps = Caps()
    assistant_budget: Caps = Caps()
    # A memory note longer than this (bytes) has its oldest sections moved to an archive note.
    memory_max_bytes: int = 32_000


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


def _caps(value: object, name: str) -> Caps:
    if value is None:
        return Caps()
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a table")
    out = {}
    for window in CAP_WINDOWS:
        number = value.get(window, 0)
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise ValueError(f"{name}.{window} must be a whole number, 0 or more")
        out[window] = number
    return Caps(**out)


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Read the settings file. A missing file gives the defaults; a bad one is an error."""
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if data.get("settings_version", Settings.settings_version) != Settings.settings_version:
        raise ValueError(f"settings_version must be {Settings.settings_version}")
    # HIPPOCAMPUS_VAULT wins over the file, so a launcher can pick the vault without editing it.
    vault = os.environ.get("HIPPOCAMPUS_VAULT") or data.get("vault", {}).get("path")
    ai = data.get("ai", {})
    defaults = Settings()
    network = data.get("network", {}).get("mode", defaults.network_mode)
    if network not in NETWORK_MODES:
        raise ValueError(f"network.mode must be one of: {', '.join(NETWORK_MODES)}")
    budget = data.get("budget", {})
    memory_limit = data.get("memory", {}).get("max_bytes", defaults.memory_max_bytes)
    if isinstance(memory_limit, bool) or not isinstance(memory_limit, int) or memory_limit < 1000:
        raise ValueError("memory.max_bytes must be a whole number of 1000 or more")
    return Settings(
        vault=(path.parent.parent / vault).resolve() if vault else None,
        provider=_provider(ai.get("provider", defaults.provider)),
        provider_model=str(ai.get("provider_model", defaults.provider_model)),
        claude_model=str(ai.get("claude_model", defaults.claude_model)),
        ollama_host=str(ai.get("ollama_host", defaults.ollama_host)),
        ollama_model=str(ai.get("ollama_model", defaults.ollama_model)),
        max_tool_calls=_tool_limit(ai.get("max_tool_calls", defaults.max_tool_calls)),
        allowed_tools=_allowed_tools(ai.get("allowed_tools")),
        network_mode=network,
        budget=_caps(budget, "budget"),
        assistant_budget=_caps(budget.get("assistant"), "budget.assistant"),
        memory_max_bytes=memory_limit,
    )


def _replace_sections(text: str, headers: tuple[str, ...], blocks: list[str]) -> str:
    """Drop the named tables from `text` and append `blocks` (each a full table, as text)."""
    kept: list[str] = []
    skipping = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            skipping = stripped in headers
        if not skipping:
            kept.append(line)
    body = "\n".join(kept).rstrip()
    return (body + "\n\n" if body else "") + "\n\n".join(blocks) + "\n"


def _write(path: Path, new: str) -> None:
    tomllib.loads(new)  # refuse to write a file that no longer parses
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(new, encoding="utf-8")
    tmp.replace(path)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def save_allowed_tools(names: tuple[str, ...] | None, path: Path = SETTINGS_PATH) -> None:
    """Write `ai.allowed_tools` to the settings file, keeping the rest. None removes the key."""
    if names is not None and not all(_TOOL_NAME.fullmatch(name) for name in names):
        raise ValueError("tool names are lowercase words with underscores")
    text = _read(path)
    lines = [line for line in text.splitlines() if not re.match(r"\s*allowed_tools\s*=", line)]
    if names is not None:
        entry = "allowed_tools = [" + ", ".join(f'"{name}"' for name in names) + "]"
        headers = [line.strip() for line in lines]
        if "[ai]" in headers:
            lines.insert(headers.index("[ai]") + 1, entry)
        else:
            lines += ["", "[ai]", entry]
    _write(path, "\n".join(lines) + "\n")


def save_vault(folder: Path, path: Path = SETTINGS_PATH) -> None:
    """Write `[vault] path` (an absolute folder) to the settings file, keeping the rest."""
    # A JSON string is also a valid TOML basic string, so json.dumps quotes and escapes the path.
    block = f"[vault]\npath = {json.dumps(str(folder))}"
    _write(path, _replace_sections(_read(path), ("[vault]",), [block]))


def save_network_mode(mode: str, path: Path = SETTINGS_PATH) -> None:
    if mode not in NETWORK_MODES:
        raise ValueError(f"network mode must be one of: {', '.join(NETWORK_MODES)}")
    _write(path, _replace_sections(_read(path), ("[network]",), [f'[network]\nmode = "{mode}"']))


def save_budget(app: Caps, assistant: Caps, path: Path = SETTINGS_PATH) -> None:
    """Write both budgets as [budget] and [budget.assistant], keeping the rest of the file."""

    def block(name: str, caps: Caps) -> str:
        values = "\n".join(f"{w} = {getattr(caps, w)}" for w in CAP_WINDOWS)
        return f"[{name}]\n{values}"

    blocks = [block("budget", app), block("budget.assistant", assistant)]
    headers = ("[budget]", "[budget.assistant]")
    _write(path, _replace_sections(_read(path), headers, blocks))
