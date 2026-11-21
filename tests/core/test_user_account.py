"""The Hippocampus account (14.09-14.12, 14.14) against a stand-in sign-in service: happy path, expired
token, offline, switching accounts, deleting, consent. The keychain is a dict here."""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import keyring
import pytest

from core import __main__ as sidecar
from core import account
from core.settings import Settings


class FakeService:
    """Answers like Supabase Auth: a code swaps for tokens only with the right verifier."""

    def __init__(self) -> None:
        self.offline = False
        self.refuse_refresh = False
        self.user = {"email": "ada@example.com", "user_metadata": {"full_name": "Ada"}}
        self.calls: list[str] = []
        self.challenge = ""
        self.deleted_on_web = False

    def __call__(self, request: urllib.request.Request) -> dict[str, Any]:
        url = request.full_url
        self.calls.append(url.split("/v1/")[1])
        if self.offline:
            raise account.Offline("no network")
        assert request.get_header("Apikey") == "anon"
        body = json.loads(request.data or b"{}")
        if "grant_type=pkce" in url:
            digest = account.base64.urlsafe_b64encode(
                account.hashlib.sha256(body["code_verifier"].encode()).digest()
            )
            if body["auth_code"] != "good" or digest.rstrip(b"=").decode() != self.challenge:
                raise account.Refused("400")
            return {
                "access_token": "a1",
                "refresh_token": "r1",
                "expires_in": 3600,
                "user": self.user,
            }
        if "grant_type=refresh_token" in url:
            if self.refuse_refresh:
                raise account.Refused("400")
            return {
                "access_token": "a2",
                "refresh_token": "r2",
                "expires_in": 3600,
                "user": self.user,
            }
        if url.endswith("/auth/v1/user") and self.deleted_on_web:
            raise account.Refused("401")  # the account was deleted on the web
        return {}


@pytest.fixture
def chain(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], str]:
    store: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(keyring, "get_password", lambda s, u: store.get((s, u)))
    monkeypatch.setattr(keyring, "set_password", lambda s, u, p: store.__setitem__((s, u), p))
    monkeypatch.setattr(keyring, "delete_password", lambda s, u: store.pop((s, u)))
    return store


def sign_in(acct: account.Account, service: FakeService, code: str = "good") -> str:
    """Do what the browser does: open the sign-in page, then come back to the local address."""
    page = urllib.parse.urlparse(acct.start()["url"])
    query = urllib.parse.parse_qs(page.query)
    assert query["provider"] == ["google"] and query["code_challenge_method"] == ["s256"]
    service.challenge = query["code_challenge"][0]
    back = query["redirect_to"][0]
    assert back.startswith("http://127.0.0.1:")
    with urllib.request.urlopen(f"{back}?code={code}", timeout=5) as reply:
        return reply.read().decode()


def make(tmp_path: Path) -> tuple[account.Account, FakeService]:
    service = FakeService()
    return account.Account(tmp_path, fetch=service, url="https://auth.test", key="anon"), service


def test_not_set_up_means_no_sign_in_and_the_app_still_works(tmp_path: Path, chain: dict) -> None:
    acct = account.Account(tmp_path, url="", key="")
    assert acct.status() == {
        "configured": False,
        "waiting": False,
        "consent": {"sync": False, "usage": False, "asked": False},
        "signed_in": False,
    }
    with pytest.raises(ValueError, match="not set up"):
        acct.start()


def test_sign_in_happy_path_keeps_tokens_only_in_the_keychain(tmp_path: Path, chain: dict) -> None:
    acct, service = make(tmp_path)
    assert "Signed in" in sign_in(acct, service)
    status = acct.status()
    assert status["signed_in"] and status["email"] == "ada@example.com" and status["name"] == "Ada"
    assert status["plan"] == "free" and not status["waiting"]
    assert "r1" in next(iter(chain.values()))
    assert not any("r1" in p.read_text() for p in tmp_path.rglob("*") if p.is_file())


def test_a_wrong_code_does_not_sign_in(tmp_path: Path, chain: dict) -> None:
    acct, service = make(tmp_path)
    assert "did not finish" in sign_in(acct, service, code="stolen")
    status = acct.status()
    assert not status["signed_in"] and "Try again" in status["problem"]


def test_an_expired_token_refreshes_and_a_revoked_one_signs_out(
    tmp_path: Path, chain: dict
) -> None:
    acct, service = make(tmp_path)
    sign_in(acct, service)
    key = next(iter(chain))
    saved = json.loads(chain[key])
    chain[key] = json.dumps({**saved, "expires_at": int(time.time()) - 5})
    assert acct.status()["signed_in"] and json.loads(chain[key])["refresh_token"] == "r2"
    chain[key] = json.dumps({**json.loads(chain[key]), "expires_at": 0})
    service.refuse_refresh = True
    status = acct.status()
    assert not status["signed_in"] and "expired" in status["problem"] and not chain


def test_offline_keeps_you_signed_in(tmp_path: Path, chain: dict) -> None:
    acct, service = make(tmp_path)
    sign_in(acct, service)
    key = next(iter(chain))
    chain[key] = json.dumps({**json.loads(chain[key]), "expires_at": 0})
    service.offline = True
    status = acct.status()
    assert status["signed_in"] and status["offline"]
    assert acct.sign_out()["signed_in"] is False and not chain  # sign-out works offline too


def test_switching_accounts(tmp_path: Path, chain: dict) -> None:
    acct, service = make(tmp_path)
    sign_in(acct, service)
    acct.sign_out()
    assert "logout" in service.calls[-1]
    service.user = {
        "email": "bo@example.com",
        "user_metadata": {},
        "app_metadata": {"plan": "supporter"},
    }
    sign_in(acct, service)
    status = acct.status()
    assert status["email"] == "bo@example.com" and status["plan"] == "supporter"


def test_deleting_an_account(tmp_path: Path, chain: dict) -> None:
    acct, service = make(tmp_path)
    with pytest.raises(ValueError, match="Sign in first"):
        acct.delete()
    sign_in(acct, service)
    service.offline = True
    with pytest.raises(ValueError, match="Nothing was deleted"):
        acct.delete()
    assert chain
    service.offline = False
    assert acct.delete()["signed_in"] is False and "delete-account" in service.calls[-1]


def test_an_account_deleted_on_the_web_signs_the_app_out(tmp_path: Path, chain: dict) -> None:
    acct, service = make(tmp_path)
    sign_in(acct, service)
    assert acct.status()["signed_in"]
    service.deleted_on_web = True
    acct._checked_at = 0  # the check runs at most every 5 minutes; force it now
    status = acct.status()
    assert not status["signed_in"] and "was deleted" in status["problem"] and not chain


def test_consent_is_off_until_chosen(tmp_path: Path, chain: dict) -> None:
    acct, _ = make(tmp_path)
    assert acct.consent() == {"sync": False, "usage": False, "asked": False}
    assert acct.set_consent(sync=True, usage=False)["consent"] == {
        "sync": True,
        "usage": False,
        "asked": True,
    }


def test_the_window_reaches_it_through_the_backend(tmp_path: Path, chain: dict) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    reply = session.dispatch({"method": "user_account"})
    assert "signed_in" in reply.get("result", reply)
    session.close()


def test_the_network_switch_off_blocks_sign_in(tmp_path: Path, chain: dict) -> None:
    from ai import network

    acct, _ = make(tmp_path)
    before = network.mode()
    network.set_mode("off")
    try:
        with pytest.raises(ValueError, match="network switch is Off"):
            acct.start()
    finally:
        network.set_mode(before)
