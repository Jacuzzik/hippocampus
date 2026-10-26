import asyncio
from typing import Any

import keyring
import pytest
from keyring.errors import KeyringError

from ai import keys
from ai.providers.base import ProviderError, Reply
from ai.router import Router, build_router
from core.settings import Settings


class Fake:
    def __init__(self, name: str, reply: Reply | None = None, error: str | None = None) -> None:
        self.name = name
        self.reply = reply or Reply(text=f"from {name}")
        self.error = error
        self.calls = 0

    async def chat(self, messages: list[dict[str, Any]], tools: list[Any]) -> Reply:
        self.calls += 1
        if self.error:
            raise ProviderError(self.error)
        return self.reply


def ask(router: Router) -> str:
    return asyncio.run(router.chat([{"role": "user", "content": "hi"}], [])).text


def test_no_key_uses_ollama() -> None:
    claude, ollama = Fake("claude"), Fake("ollama")
    assert ask(Router(None, ollama)) == "from ollama"
    assert claude.calls == 0


def test_key_uses_claude_and_falls_back_when_it_fails() -> None:
    ollama = Fake("ollama")
    assert ask(Router(Fake("claude"), ollama)) == "from claude"
    assert ask(Router(Fake("claude", error="offline"), ollama)) == "from ollama"


def test_both_failing_names_both() -> None:
    router = Router(Fake("claude", error="HTTP 500"), Fake("ollama", error="not running"))
    with pytest.raises(ProviderError, match="claude failed: HTTP 500.*ollama failed: not running"):
        ask(router)


def test_build_router_picks_claude_only_with_a_key() -> None:
    settings = Settings()
    assert build_router(settings, None).primary is None
    assert build_router(settings, "k").primary is not None


class MemoryKeyring:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def set(self, service: str, account: str, value: str) -> None:
        self.store[(service, account)] = value

    def get(self, service: str, account: str) -> str | None:
        return self.store.get((service, account))

    def delete(self, service: str, account: str) -> None:
        if (service, account) not in self.store:
            raise keyring.errors.PasswordDeleteError("missing")
        del self.store[(service, account)]


def test_key_round_trip_through_the_keychain(monkeypatch: pytest.MonkeyPatch) -> None:
    memory = MemoryKeyring()
    monkeypatch.setattr(keys.keyring, "set_password", memory.set)
    monkeypatch.setattr(keys.keyring, "get_password", memory.get)
    monkeypatch.setattr(keys.keyring, "delete_password", memory.delete)
    assert keys.get_api_key() is None
    keys.set_api_key("sk-test")
    assert keys.get_api_key() == "sk-test"
    keys.clear_api_key()
    keys.clear_api_key()  # clearing twice is fine
    assert keys.get_api_key() is None


def test_keychain_failure_means_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(service: str, account: str) -> None:
        raise KeyringError("no backend")

    monkeypatch.setattr(keys.keyring, "get_password", broken)
    assert keys.get_api_key() is None


def test_build_router_uses_the_chosen_preset_with_its_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ai.router.get_key", lambda provider: "gsk-k" if provider == "groq" else None
    )
    router = build_router(Settings(provider="groq", provider_model="llama-3.1-8b-instant"), None)
    assert router.primary is not None
    assert router.primary.name == "groq"
    assert router.primary.model == "llama-3.1-8b-instant"


def test_chosen_preset_without_a_key_falls_back_to_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai.router.get_key", lambda provider: None)
    assert build_router(Settings(provider="openai"), None).primary is None


def test_local_preset_needs_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai.router.get_key", lambda provider: None)
    router = build_router(Settings(provider="lmstudio", provider_model="qwen2.5-3b"), None)
    assert router.primary is not None and router.primary.model == "qwen2.5-3b"
