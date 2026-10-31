"""Picks the model per reply: Claude when a key is set; Ollama otherwise, or when Claude fails."""

import logging
from typing import Any

from ai.keys import get_key
from ai.providers.base import Provider, ProviderError, Reply, ToolSpec
from ai.providers.claude import ClaudeProvider
from ai.providers.claude_cli import ClaudeCliProvider, cli_ready
from ai.providers.ollama import OllamaProvider
from ai.providers.openai_compat import PRESETS, OpenAICompatProvider
from core.settings import Settings

logger = logging.getLogger("hippocampus.ai")


class Router:
    def __init__(self, primary: Provider | None, fallback: Provider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def chat(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Reply:
        failure = ""
        if self.primary is not None:
            try:
                return await self.primary.chat(messages, tools)
            except ProviderError as exc:
                failure = f"{self.primary.name} failed: {exc}; "
                logger.warning("%s", failure.rstrip("; "))
        try:
            return await self.fallback.chat(messages, tools)
        except ProviderError as exc:
            raise ProviderError(f"{failure}{self.fallback.name} failed: {exc}") from exc


def model_name(settings: Settings, api_key: str | None) -> str:
    """The model that answers now: the primary's, or Ollama's when no primary is ready."""
    if settings.provider == "claude":
        return settings.claude_model if (api_key or cli_ready()) else settings.ollama_model
    preset = PRESETS[settings.provider]
    if preset.needs_key and not get_key(settings.provider):
        return settings.ollama_model
    return settings.provider_model or (preset.models[0] if preset.models else "")


def build_router(settings: Settings, api_key: str | None, agent: str = "hippo") -> Router:
    return Router(
        _primary(settings, api_key, agent), OllamaProvider(settings.ollama_model, settings.ollama_host)
    )


def _primary(settings: Settings, api_key: str | None, agent: str = "hippo") -> Provider | None:
    if settings.provider == "claude":
        # The Claude Code CLI with the user's own login comes first; an API key is the fallback.
        if cli_ready():
            return ClaudeCliProvider(settings.claude_model, agent)
        return ClaudeProvider(api_key, settings.claude_model) if api_key else None
    preset = PRESETS[settings.provider]
    key = get_key(settings.provider)
    if preset.needs_key and not key:
        # Logged: a chosen provider that is not ready must not look like a silent switch.
        logger.warning("no key for %s; the assistant will use Ollama", settings.provider)
        return None
    model = settings.provider_model or (preset.models[0] if preset.models else "")
    return OpenAICompatProvider(settings.provider, preset.base_url, model, key)
