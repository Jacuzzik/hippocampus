"""Connecting an app saves its key in the keychain only, and its numbers obey the network switch."""

import json
from pathlib import Path

import pytest

from ai import keys, network
from core.session_apps import AppsPart


class Fake(AppsPart):
    def __init__(self, storage: Path) -> None:
        self.storage = storage
        self.notes: list[str] = []

    def note(self, _kind: str, **fields: str) -> None:
        self.notes.append(fields["text"])


@pytest.fixture
def chain(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    saved: dict[str, str] = {}
    monkeypatch.setattr(keys, "get_key", lambda name: saved.get(name))
    monkeypatch.setattr(keys, "set_key", lambda name, key: saved.__setitem__(name, key))
    monkeypatch.setattr(keys, "clear_key", lambda name: saved.pop(name, None))
    monkeypatch.setattr(keys, "key_hint", lambda name: saved[name][-4:] if name in saved else None)
    monkeypatch.setattr(network, "_mode", "converse")
    return saved


def test_connect_puts_the_key_in_the_keychain_and_only_the_shop_in_the_file(
    tmp_path: Path, chain: dict[str, str]
) -> None:
    session = Fake(tmp_path)
    answer = session.app_connect(
        {"id": "shopify", "key": " shpat_secret1234 ", "fields": {"shop": "My-Shop.myshopify.com"}}
    )
    assert chain == {"app-shopify": "shpat_secret1234"}
    assert json.loads((tmp_path / "apps.json").read_text()) == {
        "shopify": {"shop": "my-shop.myshopify.com"}
    }
    row = next(row for row in answer["apps"] if row["id"] == "shopify")
    assert (row["connected"], row["hint"]) == (True, "1234")
    assert "shpat_secret1234" not in json.dumps(answer)
    assert "shpat_secret1234" not in " ".join(session.notes)
    session.app_disconnect({"id": "shopify"})
    assert chain == {}
    assert json.loads((tmp_path / "apps.json").read_text()) == {}


def test_a_bad_key_or_setting_is_refused_and_nothing_is_saved(
    tmp_path: Path, chain: dict[str, str]
) -> None:
    session = Fake(tmp_path)
    with pytest.raises(ValueError, match="Paste the key"):
        session.app_connect({"id": "stripe", "key": "  "})
    with pytest.raises(ValueError, match="does not look like a key"):
        session.app_connect({"id": "stripe", "key": "a\nb"})
    with pytest.raises(ValueError, match="must look like"):
        session.app_connect({"id": "shopify", "key": "k", "fields": {"shop": "evil.com/x"}})
    with pytest.raises(ValueError, match="not in the catalogue"):
        session.app_connect({"id": "nope", "key": "k"})
    assert chain == {}
    assert not (tmp_path / "apps.json").exists()


def test_numbers_need_a_connection_and_a_network_that_allows_going_out(
    tmp_path: Path, chain: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Fake(tmp_path)
    with pytest.raises(ValueError, match="not connected"):
        session.app_board({"id": "todoist"})
    session.app_connect({"id": "todoist", "key": "tok"})
    session._apps_fetch = lambda url, headers: (200, b'{"results": [1, 2, 3]}')
    board = session.app_board({"id": "todoist"})
    assert board["name"] == "Todoist"
    assert [row["value"] for row in board["numbers"]] == ["3", "3"]
    for blocked in ("off", "listen"):
        monkeypatch.setattr(network, "_mode", blocked)
        with pytest.raises(ValueError, match="cannot be read"):
            session.app_board({"id": "todoist"})
