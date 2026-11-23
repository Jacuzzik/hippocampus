"""The providers, money, vault and GitHub dashboards read real logs and the user's own numbers."""

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from core import github_repos, provider_usage, spend_plans, vault_board


def test_provider_usage_reads_each_tool_s_own_log_by_model_and_day(tmp_path: Path) -> None:
    home = tmp_path / "home"
    claude = home / ".claude" / "projects" / "-work"
    claude.mkdir(parents=True)
    reply = {
        "timestamp": "2026-11-23T10:00:00Z",
        "message": {
            "id": "m1",
            "model": "claude-x",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    }
    # The same reply logged twice (one line per content block) counts once.
    (claude / "s.jsonl").write_text(json.dumps(reply) + "\n" + json.dumps(reply) + "\n")
    codex = home / ".codex" / "sessions" / "2026" / "11" / "23"
    codex.mkdir(parents=True)
    rows = [
        {"type": "turn_context", "payload": {"model": "gpt-x"}},
        {
            "timestamp": "2026-11-23T11:00:00Z",
            "payload": {"type": "token_count", "info": {"last_token_usage": {"total_tokens": 7}}},
        },
    ]
    (codex / "rollout-2026-11-23-a.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (home / ".gemini" / "antigravity-cli" / "conversations").mkdir(parents=True)
    (home / ".gemini" / "antigravity-cli" / "conversations" / "a.db").write_bytes(b"")
    found = {
        p["id"]: p for p in provider_usage.report(tmp_path, home, date(2026, 11, 23))["providers"]
    }
    assert (found["claude"]["today"], found["claude"]["models"]) == (
        15,
        [{"model": "claude-x", "tokens": 15}],
    )
    assert found["codex"]["month"] == 7 and found["codex"]["days"][-1] == 7
    assert found["antigravity"]["month"] == 0 and "1 conversations" in found["antigravity"]["note"]


def test_every_supported_provider_is_listed_and_opencode_is_split_by_provider(
    tmp_path: Path,
) -> None:
    import sqlite3

    home = tmp_path / "home"
    db = home / ".local" / "share" / "opencode" / "opencode.db"
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:
        conn.execute("create table message (time_created integer, data text)")
        stamp = 1_795_400_000_000  # 2026-11-22
        for provider, model, tokens in [
            ("openai", "gpt-x", 30),
            ("ollama", "qwen", 5),
            ("opencode", "big-pickle", 9),
        ]:
            data = {"providerID": provider, "modelID": model, "tokens": {"total": tokens}}
            conn.execute("insert into message values (?, ?)", (stamp, json.dumps(data)))
    found = {
        p["id"]: p
        for p in provider_usage.report(
            tmp_path,
            home,
            date(2026, 11, 23),
            has_key=lambda provider: provider == "groq",
            which=lambda _name: None,
        )["providers"]
    }
    assert list(found) == [
        "claude", "codex", "gemini-cli", "antigravity", "opencode", "ollama",
        "openai", "xai", "moonshot", "gemini", "qwen", "deepseek", "mistral", "groq",
        "openrouter", "app",
    ]  # fmt: skip
    assert (found["openai"]["month"], found["openai"]["setup"]) == (30, "used")
    assert (found["ollama"]["month"], found["opencode"]["month"]) == (5, 9)
    assert found["groq"]["setup"] == "key saved" and found["groq"]["found"]
    assert found["xai"]["setup"] == "not set up" and not found["xai"]["found"]


def test_money_is_the_user_s_plans_plus_their_price_times_real_tokens(tmp_path: Path) -> None:
    path = tmp_path / "plans.json"
    plans = spend_plans.save(
        path,
        {
            "currency": "USD",
            "plans": [
                {"name": "Claude Max", "provider": "claude", "monthly": 200},
                {"name": "Codex API", "provider": "codex", "per_million": 2},
            ],
        },
    )
    usage = {
        "days": 2,
        "providers": [
            {"id": "claude", "name": "Claude Code", "month": 9_000_000, "days": [1, 1]},
            {"id": "codex", "name": "Codex", "month": 3_000_000, "days": [1_000_000, 2_000_000]},
        ],
    }
    money = spend_plans.report(plans, usage, date(2026, 11, 10))
    assert (money["fixed"], money["metered"], money["total"]) == (200, 6, 206)
    assert money["projected"] == 218  # 6 over 10 days is 18 over 30
    assert money["daily"] == [2, 4]
    assert spend_plans.load(path)["plans"][1]["per_million"] == 2
    for bad, reason in [
        ({"currency": "XYZ"}, "currency"),
        ({"plans": [{"name": ""}]}, "needs a name"),
        ({"plans": [{"name": "x", "monthly": -1}]}, "from 0"),
    ]:
        with pytest.raises(ValueError, match=reason):
            spend_plans.check(bad)


def test_vault_counts_projects_important_daily_orphans_and_reads_the_agent_summary(
    tmp_path: Path,
) -> None:
    graph = {
        "nodes": [
            {"id": "Projects/Alpha/plan.md", "title": "Plan", "tags": []},
            {"id": "Projects/Alpha/notes.md", "title": "Notes", "tags": ["important"]},
            {"id": "Projects/Beta.md", "title": "Beta", "tags": []},
            {"id": "Ideas/gamma.md", "title": "Gamma", "tags": ["project"]},
            {"id": "Daily/2026-11-23.md", "title": "Today", "tags": [], "memory": True},
        ],
        "edges": [["Projects/Beta.md", "Ideas/gamma.md"]],
    }
    now = 10**18
    found = vault_board.stats(graph, {"Daily/2026-11-23.md": now}, 2, now)
    assert (found["projects"], found["important"], found["daily"], found["memory"]) == (3, 1, 1, 1)
    assert (found["orphans"], found["broken"], found["changed_week"]) == (3, 2, 1)
    path = tmp_path / "insights.json"
    assert vault_board.load_insights(path) is None
    path.write_text(
        json.dumps({"summary": "Two projects.", "numbers": [{"label": "Active", "value": 2}]})
    )
    assert vault_board.load_insights(path)["numbers"] == [
        {"label": "Active", "value": "2", "note": ""}
    ]


def test_github_lists_every_repository_with_the_agents_work_from_their_folders(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "agent"
    (folder / ".git").mkdir(parents=True)

    def run(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["gh", "repo", "list"]:
            out = json.dumps(
                [
                    {"nameWithOwner": "me/old", "pushedAt": "2026-01-01"},
                    {"nameWithOwner": "me/app", "pushedAt": "2026-11-20", "isPrivate": True},
                ]
            )
        elif "remote" in args:
            out = "git@github.com:me/app.git\n"
        else:
            out = "2026-11-22\tFix the tabs\n2026-11-21\tAdd the calendar\n"
        return subprocess.CompletedProcess(args, 0, out, "")

    found = github_repos.board([("ada", "Ada", folder)], lambda _n: "/bin/gh", run)
    assert [r["repo"] for r in found["repos"]] == ["me/app", "me/old"]
    work = found["repos"][0]["agents"][0]
    assert (work["name"], work["commits"], work["subjects"][0]) == ("Ada", 2, "Fix the tabs")

    def signed_out(args: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args, 1, "", "To get started with GitHub CLI, please run: gh auth login"
        )

    assert "gh auth login" in github_repos.board([], lambda _n: "/bin/gh", signed_out)["error"]


def test_subscriptions_are_checked_and_a_cancelled_one_past_its_date_is_expired() -> None:
    from datetime import date

    from core import spend_plans

    plans = spend_plans.check(
        {
            "currency": "USD",
            "plans": [],
            "subs": [
                {"name": "iCloud+", "store": "apple", "price": 2.99, "period": "month",
                 "status": "active", "renews": "2026-12-01"},
                {"name": "Arcade", "store": "apple", "price": 60, "period": "year",
                 "status": "cancelled", "renews": "2026-11-01"},
                {"name": "Music", "store": "other", "price": 5, "status": "cancelled",
                 "renews": "2026-12-30", "link": "https://example.com/renew"},
            ],
        }
    )  # fmt: skip
    rows = spend_plans.sub_rows(plans["subs"], date(2026, 11, 23))
    assert [(r["name"], r["state"]) for r in rows] == [
        ("iCloud+", "active"),
        ("Arcade", "expired"),
        ("Music", "cancelled"),
    ]
    assert rows[0]["manage"] == "https://apps.apple.com/account/subscriptions"
    assert rows[2]["resubscribe"] == "https://example.com/renew"
    report = spend_plans.report(plans, {"providers": [], "days": 0}, date(2026, 11, 23))
    assert report["subs_monthly"] == 2.99
    assert report["fixed"] == 2.99


def test_a_subscription_link_must_be_https() -> None:
    import pytest

    from core import spend_plans

    with pytest.raises(ValueError, match="https"):
        spend_plans.check({"subs": [{"name": "x", "link": "javascript:alert(1)"}]})


def test_wallets_are_checked_totalled_per_currency_and_open_their_own_page() -> None:
    import pytest

    from core import spend_plans

    plans = spend_plans.check(
        {
            "wallets": [
                {"name": "Store", "kind": "stripe", "balance": 120.5, "currency": "GBP",
                 "updated": "2026-11-23"},
                {"name": "PayPal", "kind": "paypal", "balance": 40, "currency": "USD"},
                {"name": "Cold", "kind": "crypto", "balance": 10, "currency": "USD",
                 "link": "https://example.com/wallet"},
            ]
        }
    )  # fmt: skip
    rows = spend_plans.wallet_rows(plans["wallets"])
    assert [r["name"] for r in rows] == ["Store", "PayPal", "Cold"]
    assert rows[0]["open"] == "https://dashboard.stripe.com/balance/overview"
    assert rows[2]["open"] == "https://example.com/wallet"
    assert spend_plans.wallet_totals(plans["wallets"]) == {"GBP": 120.5, "USD": 50.0}
    with pytest.raises(ValueError, match="choices"):
        spend_plans.check({"wallets": [{"name": "x", "kind": "bitcoin-exchange"}]})
    with pytest.raises(ValueError, match="https"):
        spend_plans.check({"wallets": [{"name": "x", "link": "http://example.com"}]})
