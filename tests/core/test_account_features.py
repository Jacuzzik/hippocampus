"""What an account unlocks (14.02 sync, 14.04 share links, 14.06 limits, 14.07 usage history), against a
stand-in service. The keychain is a dict; the database is a few lists."""

import json
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from core import account, account_sync
from tests.core.test_user_account import FakeService, chain, make, sign_in  # noqa: F401 (fixture)


class FakeData(FakeService):
    """Adds the database: sync rows, usage rows and share links, with the share limits of the SQL file."""

    def __init__(self) -> None:
        super().__init__()
        self.sync: dict[str, dict[str, str]] = {}
        self.usage: dict[str, int] = {}
        self.links: list[dict[str, Any]] = []

    def __call__(self, request: urllib.request.Request) -> Any:  # noqa: ANN401
        url = request.full_url
        if "/rest/v1/" not in url:
            return super().__call__(request)
        if self.offline:
            raise account.Offline("no network")
        assert request.get_header("Authorization", "").startswith("Bearer a")
        body = json.loads(request.data or b"null")
        path = url.split("/rest/v1/")[1]
        method = request.get_method()
        if path.startswith("sync_items") and method == "POST":
            for row in body:
                self.sync[row["kind"]] = {"body": row["body"], "updated_at": row["updated_at"]}
            return {}
        if path.startswith("sync_items"):
            return [{"kind": k, **v} for k, v in self.sync.items()]
        if path.startswith("usage_days"):
            self.usage.update({r["day"]: r["tokens"] for r in body})
            return {}
        if path == "rpc/create_share":
            if len(self.links) >= 20:
                raise account.Refused("you have 20 live links; delete one first")
            link = {
                "id": f"0000-{len(self.links):04d}",
                "title": body["p_title"],
                "expires_at": "x",
            }
            self.links.append({**link, "body": body["p_body"], "password": body["p_password"]})
            return [{"id": link["id"], "expires_at": "x"}]
        if path.startswith("shares") and method == "DELETE":
            gone = path.split("id=eq.")[1]
            self.links = [x for x in self.links if x["id"] != gone]
            return {}
        if path.startswith("shares"):
            return [{"id": x["id"], "title": x["title"], "expires_at": "x"} for x in self.links]
        raise AssertionError(path)


pytestmark = pytest.mark.usefixtures("chain")


def signed_in(tmp_path: Path) -> tuple[account.Account, FakeData]:
    acct, _ = make(tmp_path)
    service = FakeData()
    acct.fetch = service
    sign_in(acct, service)
    return acct, service


def test_everything_needs_a_sign_in(tmp_path: Path) -> None:
    acct, _ = make(tmp_path)
    for call in (acct.sync_fetch, acct.shares):
        with pytest.raises(ValueError, match="Sign in first"):
            call()


def test_save_and_get_moves_agents_and_settings_but_keeps_this_vault(
    tmp_path: Path,
) -> None:
    acct, service = signed_in(tmp_path)
    a_agents, a_settings = tmp_path / "a" / "agents.json", tmp_path / "a" / "settings.toml"
    a_agents.parent.mkdir()
    a_agents.write_text(json.dumps([{"id": "1", "name": "Pam"}]))
    a_settings.write_text('[ai]\nprovider = "claude"\n\n[vault]\npath = "/home/a/notes"\n')
    result = account_sync.save(acct, a_agents, a_settings, tmp_path / "none.jsonl")
    assert result == {"saved": ["agents", "settings"], "usage_days": 0}
    assert service.usage == {}  # usage history is off by default

    b_agents, b_settings = tmp_path / "b" / "agents.json", tmp_path / "b" / "settings.toml"
    b_agents.parent.mkdir()
    b_agents.write_text("[]")
    b_settings.write_text('[ai]\nprovider = "gemini"\n\n[vault]\npath = "/home/b/notes"\n')
    got = account_sync.fetch(acct, b_agents, b_settings)
    assert got["fetched"] == ["agents", "settings"]
    assert json.loads(b_agents.read_text()) == [{"id": "1", "name": "Pam"}]
    text = b_settings.read_text()
    assert 'provider = "claude"' in text and "/home/b/notes" in text and "/home/a/" not in text
    assert "gemini" in (tmp_path / "b" / "settings.toml.before-sync").read_text()
    assert (tmp_path / "b" / "agents.json.before-sync").read_text() == "[]"


def test_getting_from_an_empty_account_changes_nothing(tmp_path: Path) -> None:
    acct, _ = signed_in(tmp_path)
    agents = tmp_path / "agents.json"
    agents.write_text("[]")
    with pytest.raises(ValueError, match="Nothing is saved"):
        account_sync.fetch(acct, agents, tmp_path / "settings.toml")
    assert agents.read_text() == "[]"


def test_usage_history_sends_only_tokens_per_day_and_only_when_turned_on(
    tmp_path: Path,
) -> None:
    acct, service = signed_in(tmp_path)
    ledger = tmp_path / "usage.jsonl"
    now = datetime.now().astimezone()
    rows = [
        {"ts": now.isoformat(), "agent": "secret-agent", "tokens": 100},
        {"ts": now.isoformat(), "agent": "pam", "tokens": 50},
        {"ts": "2001-01-01T00:00:00+00:00", "agent": "old", "tokens": 9},
    ]
    ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
    acct.set_consent(sync=True, usage=True)
    result = account_sync.save(acct, tmp_path / "agents.json", tmp_path / "s.toml", ledger)
    assert result["usage_days"] == 1
    assert service.usage == {now.date().isoformat(): 150}


def test_share_links_are_made_listed_limited_and_deleted(tmp_path: Path) -> None:
    acct, service = signed_in(tmp_path)
    made = acct.share_create("Plan", "# Plan\nsecret", "long enough", 60)
    assert made["url"] == f"{account.SITE_URL}/share.html#0000-0000"
    assert [s["title"] for s in acct.shares()] == ["Plan"]
    for _ in range(19):
        acct.share_create("More", "x", "long enough", 5)
    with pytest.raises(ValueError, match="20 live links"):
        acct.share_create("One too many", "x", "long enough", 5)
    assert len(acct.shares()) == 20
    acct.share_delete("0000-0000")
    assert "Plan" not in [s["title"] for s in acct.shares()]
    with pytest.raises(ValueError, match="not a link id"):
        acct.share_delete("x; drop table")
    assert all(link["password"] == "long enough" for link in service.links)  # hashed by the server


def test_offline_says_so_and_changes_nothing(tmp_path: Path) -> None:
    acct, service = signed_in(tmp_path)
    service.offline = True
    with pytest.raises(ValueError, match="Could not reach"):
        acct.shares()


def test_plan_is_free_unless_the_owner_set_supporter(tmp_path: Path) -> None:
    """14.05: the plan comes from app_metadata, which only the owner can write."""
    acct, service = make(tmp_path)
    sign_in(acct, service)
    assert acct.status()["plan"] == "free"
    service.user["app_metadata"] = {"plan": "supporter"}
    acct.sign_out()
    sign_in(acct, service)
    assert acct.status()["plan"] == "supporter"
    service.user["user_metadata"] = {"plan": "supporter"}  # a user cannot give themselves the plan
    service.user.pop("app_metadata")
    acct.sign_out()
    sign_in(acct, service)
    assert acct.status()["plan"] == "free"


def test_a_banned_account_is_signed_out_with_a_plain_reason(tmp_path: Path) -> None:
    """14.06: a ban set by the owner ends the sign-in and says so; the app keeps working."""
    acct, service = make(tmp_path)
    sign_in(acct, service)
    service.deleted_on_web = True
    acct._checked_at = 0
    original = service.__call__

    def banned(request: urllib.request.Request) -> Any:  # noqa: ANN401
        if request.full_url.endswith("/auth/v1/user"):
            raise account.Refused("User is banned")
        return original(request)

    acct.fetch = banned
    status = acct.status()
    assert status["signed_in"] is False and "suspended" in status["problem"]


def test_the_database_holds_the_limits_a_changed_app_cannot_skip() -> None:
    """14.06: the limits are in the SQL file, not only in the app. Static check: no database runs here."""
    sql = (
        Path(__file__).parents[2] / "supabase/migrations/20261118_account_features.sql"
    ).read_text()
    for rule in (
        "enable row level security",
        ">= 20",  # live links
        ">= 50",  # links per day
        "hit.failed >= 10",  # wrong passwords lock a link
        "octet_length(body) <= 262144",  # sync size
        "octet_length(body) <= 204800",  # share size
        "revoke all on function public.create_share",
    ):
        assert rule in sql
    for table in ("sync_items", "usage_days", "shares"):
        assert f"alter table public.{table} enable row level security" in sql
