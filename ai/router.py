"""Picks the model per reply: Claude when a key is set; Ollama otherwise, or when Claude fails."""

import logging
from typing import Any

from ai.providers.base import Provider, ProviderError, Reply, ToolSpec
from ai.providers.claude import ClaudeProvider
from ai.providers.ollama import OllamaProvider
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


def build_router(settings: Settings, api_key: str | None) -> Router:
    primary = ClaudeProvider(api_key, settings.claude_model) if api_key else None
    return Router(primary, OllamaProvider(settings.ollama_model, settings.ollama_host))
