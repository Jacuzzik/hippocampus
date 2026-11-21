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


def test_account_status_never_returns_the_key(
    keychain: Keychain, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.router.cli_ready", lambda: False)  # the CLI would count as a key
    s = session(tmp_path)
    account = s.dispatch({"method": "account"})
    assert (account["claude"], account["model"]) == (False, "qwen2.5:1.5b")
    assert account["ready"] is False  # nothing set up: replies depend on Ollama
    keychain.set("sk-test")
    account = s.dispatch({"method": "account"})
    assert (account["claude"], account["model"]) == (True, "claude-sonnet-5-5")
    assert account["ready"] is True
    assert "sk-test" not in str(s.dispatch({"method": "account"}))


def test_the_old_single_key_calls_are_gone(tmp_path: Path) -> None:
    for method in ("sign_in", "sign_out"):
        with pytest.raises(ValueError, match="Unknown method|unknown method"):
            session(tmp_path).dispatch({"method": method})


def test_keychain_failure_is_a_plain_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def broken(*_: object) -> None:
        raise KeyringError("no backend")

    monkeypatch.setattr(sidecar, "clear_api_key", broken)
    with pytest.raises(ValueError, match="keychain is not available"):
        session(tmp_path).dispatch({"method": "remove_data"})


def test_remove_data_deletes_the_index_and_the_key_but_not_the_vault(
    keychain: Keychain, tmp_path: Path
) -> None:
    storage = tmp_path / "storage"
    (storage / "index").mkdir(parents=True)
    (storage / "index" / "abc.sqlite3").write_text("cache", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("keep me", encoding="utf-8")
    keychain.set("sk-test")
    s = sidecar.Session(storage, Settings(), emit=lambda event: None)

    assert s.dispatch({"method": "remove_data"}) == {"claude": False}
    assert not (storage / "index").exists()
    assert keychain.key is None
    assert (vault / "note.md").read_text(encoding="utf-8") == "keep me"
