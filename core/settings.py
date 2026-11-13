"""Reads config/settings.toml. It holds no secrets: API keys live in the OS keychain."""

import json
import logging
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ai.network import MODES as NETWORK_MODES

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.toml"
# The hive (agent inboxes and outboxes) lives outside the app folder, so agents' Edit denial for the app folder does not block their outbox.
# HIPPOCAMPUS_HIVE moves it, so a test (or a second copy of the app) never shares the real one.
HIVE_DIR = Path(os.environ.get("HIPPOCAMPUS_HIVE") or Path.home() / ".hippocampus" / "hive")


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
    # On: every agent gets a fenced shell and its program runs in the operating-system sandbox.
    # Off: only the main agent has a (fenced) shell, as before.
    agent_shell: bool = False


logger = logging.getLogger("hippocampus.core")

# One list of every setting the file may hold: its dotted key, type, default and one line of help.
# `load_settings` warns about a key not listed here, the `settings` call returns the list, and a test checks
# that every key in config/settings.toml and every Settings field is in it.
SCHEMA: tuple[dict[str, object], ...] = (
    {
        "key": "settings_version",
        "type": "int",
        "default": 1,
        "help": "Version of this file's layout.",
    },
    {
        "key": "vault.path",
        "type": "path",
        "default": None,
        "help": "The notes folder, relative to the app folder or absolute.",
    },
    {
        "key": "ai.provider",
        "type": "text",
        "default": "claude",
        "help": "The provider for the main agent: claude or a preset.",
    },
    {
        "key": "ai.provider_model",
        "type": "text",
        "default": "",
        "help": "A model for the chosen preset; empty uses its first.",
    },
    {
        "key": "ai.claude_model",
        "type": "text",
        "default": "claude-sonnet-5-5",
        "help": "The Claude model.",
    },
    {
        "key": "ai.ollama_host",
        "type": "text",
        "default": "http://127.0.0.1:11434",
        "help": "Where the Ollama server listens.",
    },
    {
        "key": "ai.ollama_model",
        "type": "text",
        "default": "qwen2.5:1.5b",
        "help": "The model Ollama runs.",
    },
    {
        "key": "ai.max_tool_calls",
        "type": "int",
        "default": 20,
        "help": "Tool calls in one request before it pauses.",
    },
    {
        "key": "ai.allowed_tools",
        "type": "list",
        "default": None,
        "help": "Tools the assistant may use; none listed means all.",
    },
    {
        "key": "network.mode",
        "type": "choice",
        "default": "converse",
        "help": "Outbound switch: off, listen, converse or open.",
    },
    *(
        {
            "key": f"budget.{w}",
            "type": "int",
            "default": 0,
            "help": f"App token cap, {w.replace('_', ' ')} window. 0 is no cap.",
        }
        for w in CAP_WINDOWS
    ),
    *(
        {
            "key": f"budget.assistant.{w}",
            "type": "int",
            "default": 0,
            "help": f"Assistant token cap, {w.replace('_', ' ')} window. 0 is no cap.",
        }
        for w in CAP_WINDOWS
    ),
    {
        "key": "memory.max_bytes",
        "type": "int",
        "default": 32000,
        "help": "A memory note longer than this has its oldest sections archived.",
    },
    {
        "key": "agents.shell",
        "type": "bool",
        "default": False,
        "help": "Give every agent a fenced shell in the sandbox.",
    },
)
SCHEMA_KEYS = frozenset(str(row["key"]) for row in SCHEMA)


def dotted_keys(data: dict[str, object], prefix: str = "") -> list[str]:
    """Every key in a parsed settings file, as dotted paths (`ai.provider`)."""
    keys: list[str] = []
    for name, value in data.items():
        path = f"{prefix}{name}"
        if isinstance(value, dict):
            keys += dotted_keys(value, f"{path}.")
        else:
            keys.append(path)
    return keys


def unknown_keys(data: dict[str, object]) -> list[str]:
    """Keys in the file that no setting uses."""
    return [key for key in dotted_keys(data) if key not in SCHEMA_KEYS]


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


# Every provider the Monitor's engine switch offers (app/ui/control/model.ts AGENT_PROVIDERS).
ENGINE_PROVIDERS = (
    "claude",
    "codex",
    "gemini-cli",
    "antigravity",
    "ollama",
    "openai",
    "xai",
    "moonshot",
    "gemini",
    "qwen",
    "deepseek",
    "mistral",
    "groq",
    "openrouter",
)


# The models each provider offers in the Monitor's engine switch. Mirrors AGENT_MODELS in app/ui/control/model.ts;
# tests/core/test_settings.py fails if the two drift apart. An empty list means the provider offers no model to pick.
ENGINE_MODELS: dict[str, tuple[str, ...]] = {
    "claude": ("claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"),
    "codex": ("gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-luna", "gpt-5.5", "gpt-5.4", "gpt-5.3-codex"),
    "antigravity": (
        "gemini-3.8-flash-high",
        "gemini-3.8-flash-medium",
        "gemini-3.8-flash-low",
        "claude-sonnet-4-6",
        "claude-opus-4-6-thinking",
        "gpt-oss-120b-medium",
    ),
    "gemini-cli": (
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ),
    "ollama": ("qwen2.5:1.5b",),
    "openai": (
        "gpt-6.1-sol",
        "gpt-6.1-terra",
        "gpt-6-luna",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
    ),
    "xai": ("grok-4.6", "grok-4.5", "grok-4.3", "grok-latest"),
    "moonshot": ("kimi-k3", "kimi-k2.6", "moonshot-v1-8k"),
    "gemini": (
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-lite",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ),
    "qwen": ("qwen3.8-max", "qwen3.7-plus", "qwen3.8-flash"),
    "deepseek": ("deepseek-v4-pro", "deepseek-flash"),
    "mistral": ("mistral-large-3", "mistral-small-4", "codestral-latest"),
    "groq": ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b"),
    "openrouter": ("anthropic/claude-sonnet-4.5", "openai/gpt-4o", "google/gemini-2.5-pro"),
}


def _provider(value: object) -> str:
    if value not in ENGINE_PROVIDERS:
        raise ValueError(f"ai.provider must be one of: {', '.join(ENGINE_PROVIDERS)}")
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
    for key in unknown_keys(data):
        logger.warning("Settings file %s: %s is not a setting and is ignored", path.name, key)
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
    agent_shell = data.get("agents", {}).get("shell", defaults.agent_shell)
    if not isinstance(agent_shell, bool):
        raise ValueError("agents.shell must be true or false")
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
        agent_shell=agent_shell,
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


def save_agent_shell(on: bool, path: Path = SETTINGS_PATH) -> None:
    """Write `[agents] shell` to the settings file, keeping the rest."""
    if not isinstance(on, bool):
        raise ValueError("agents.shell must be true or false")
    _write(
        path,
        _replace_sections(
            _read(path), ("[agents]",), [f"[agents]\nshell = {'true' if on else 'false'}"]
        ),
    )


def save_engine(provider: str, model: str, path: Path = SETTINGS_PATH) -> None:
    """Set the main agent's provider and model, changing only those lines of [ai]."""
    if not provider or not model:
        raise ValueError("pick a provider and a model")
    # Checked before anything is written, so a refused choice never leaves the settings file half changed.
    if provider not in ENGINE_PROVIDERS:
        raise ValueError(
            f"{provider} is not a provider in this app. Pick one of: {', '.join(ENGINE_PROVIDERS)}"
        )
    if any(ch in model for ch in '"\\\n\r'):
        raise ValueError(f"{model!r} is not a valid model name")
    offered = ENGINE_MODELS.get(provider, ())
    if model not in offered:
        if not offered:
            raise ValueError(f"{provider} has no models in this app to pick from")
        raise ValueError(
            f"{model} is not a model {provider} offers here. Pick one of: {', '.join(offered)}"
        )
    section, out = "", []
    for line in _read(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped
        if section == "[ai]" and stripped.startswith("provider ="):
            line = f'provider = "{provider}"'
        elif section == "[ai]" and stripped.startswith("provider_model ="):
            line = f'provider_model = "{model}"' if provider != "claude" else line
        elif section == "[ai]" and stripped.startswith("claude_model =") and provider == "claude":
            line = f'claude_model = "{model}"'
        out.append(line)
    _write(path, "\n".join(out) + "\n")


def save_budget(app: Caps, assistant: Caps, path: Path = SETTINGS_PATH) -> None:
    """Write both budgets as [budget] and [budget.assistant], keeping the rest of the file."""

    def block(name: str, caps: Caps) -> str:
        values = "\n".join(f"{w} = {getattr(caps, w)}" for w in CAP_WINDOWS)
        return f"[{name}]\n{values}"

    blocks = [block("budget", app), block("budget.assistant", assistant)]
    headers = ("[budget]", "[budget.assistant]")
    _write(path, _replace_sections(_read(path), headers, blocks))
