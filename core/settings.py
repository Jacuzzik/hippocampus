"""Reads config/settings.toml. It holds no secrets: API keys live in the OS keychain."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.toml"


@dataclass(frozen=True)
class Settings:
    vault: Path | None = None
    claude_model: str = "claude-sonnet-5-5"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b"
    # Tool calls the assistant may make in one request before it pauses for the user to continue.
    max_tool_calls: int = 20


def _tool_limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("ai.max_tool_calls must be a whole number of 1 or more")
    return value


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Read the settings file. A missing file gives the defaults; a bad one is an error."""
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    # HIPPOCAMPUS_VAULT wins over the file, so a launcher can pick the vault without editing it.
    vault = os.environ.get("HIPPOCAMPUS_VAULT") or data.get("vault", {}).get("path")
    ai = data.get("ai", {})
    defaults = Settings()
    return Settings(
        vault=(path.parent.parent / vault).resolve() if vault else None,
        claude_model=str(ai.get("claude_model", defaults.claude_model)),
        ollama_host=str(ai.get("ollama_host", defaults.ollama_host)),
        ollama_model=str(ai.get("ollama_model", defaults.ollama_model)),
        max_tool_calls=_tool_limit(ai.get("max_tool_calls", defaults.max_tool_calls)),
    )
