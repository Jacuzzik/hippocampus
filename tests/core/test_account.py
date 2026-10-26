from pathlib import Path

import pytest
from keyring.errors import KeyringError

from core import __main__ as sidecar
from core.settings import Settings


class Keychain:
    def __init__(self) -> None:
        self.key: str | None = None

    def set(self, key: str) -> None:
        self.key = key

    def clear(self) -> None:
        self.key = None


@pytest.fixture
def keychain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Keychain:
    store = Keychain()
    monkeypatch.setattr(sidecar, "set_api_key", store.set)
    monkeypatch.setattr(sidecar, "clear_api_key", store.clear)
    monkeypatch.setattr(sidecar, "get_api_key", lambda: store.key)
    return store


def session(tmp_path: Path) -> sidecar.Session:
    return sidecar.Session(tmp_path, Settings(), emit=lambda event: None)


def test_sign_in_saves_the_key_and_status_never_returns_it(
    keychain: Keychain, tmp_path: Path
) -> None:
    s = session(tmp_path)
    assert s.dispatch({"method": "account"}) == {"claude": False, "model": "qwen2.5:1.5b"}
    assert s.dispatch({"method": "sign_in", "key": " sk-test "}) == {"claude": True}
    assert keychain.key == "sk-test"
    assert s.dispatch({"method": "account"}) == {"claude": True, "model": "claude-sonnet-5-5"}
    assert "sk-test" not in str(s.dispatch({"method": "account"}))


def test_sign_in_rejects_an_empty_key(keychain: Keychain, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        session(tmp_path).dispatch({"method": "sign_in", "key": "   "})
    assert keychain.key is None


def test_sign_out_removes_the_key(keychain: Keychain, tmp_path: Path) -> None:
    s = session(tmp_path)
    s.dispatch({"method": "sign_in", "key": "sk-test"})
    assert s.dispatch({"method": "sign_out"}) == {"claude": False}
    assert keychain.key is None


def test_keychain_failure_is_a_plain_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def broken(*_: object) -> None:
        raise KeyringError("no backend")

    monkeypatch.setattr(sidecar, "set_api_key", broken)
    monkeypatch.setattr(sidecar, "clear_api_key", broken)
    s = session(tmp_path)
    with pytest.raises(ValueError, match="keychain is not available"):
        s.dispatch({"method": "sign_in", "key": "sk-test"})
    with pytest.raises(ValueError, match="keychain is not available"):
        s.dispatch({"method": "sign_out"})
