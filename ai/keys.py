"""API keys for model providers, kept in the OS keychain. Never written to a file or a log."""

import logging

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

logger = logging.getLogger("hippocampus.ai")

SERVICE = "hippocampus"
ACCOUNT = "anthropic-api-key"  # Claude's key keeps its original keychain entry


def _account(provider: str) -> str:
    return ACCOUNT if provider == "claude" else f"{provider}-api-key"


def get_key(provider: str) -> str | None:
    """The stored key for a provider, or None when there is none or the keychain is unavailable."""
    try:
        return keyring.get_password(SERVICE, _account(provider)) or None
    except KeyringError:
        logger.warning("OS keychain unavailable; %s key not read", provider, exc_info=True)
        return None


def set_key(provider: str, key: str) -> None:
    keyring.set_password(SERVICE, _account(provider), key)


def clear_key(provider: str) -> None:
    try:
        keyring.delete_password(SERVICE, _account(provider))
    except PasswordDeleteError:
        pass


def get_api_key() -> str | None:
    return get_key("claude")


def set_api_key(key: str) -> None:
    set_key("claude", key)


def clear_api_key() -> None:
    clear_key("claude")
