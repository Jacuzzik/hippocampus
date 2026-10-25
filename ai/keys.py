"""The Claude API key, kept in the OS keychain. It is never written to a file or a log."""

import logging

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

logger = logging.getLogger("hippocampus.ai")

SERVICE = "hippocampus"
ACCOUNT = "anthropic-api-key"


def get_api_key() -> str | None:
    """The stored key, or None when there is none or the keychain is unavailable."""
    try:
        return keyring.get_password(SERVICE, ACCOUNT) or None
    except KeyringError:
        logger.warning("OS keychain unavailable; the assistant will use Ollama only", exc_info=True)
        return None


def set_api_key(key: str) -> None:
    keyring.set_password(SERVICE, ACCOUNT, key)


def clear_api_key() -> None:
    try:
        keyring.delete_password(SERVICE, ACCOUNT)
    except PasswordDeleteError:
        pass
