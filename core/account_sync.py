"""Sync by button (plan 14.02) and usage history (14.07), between this computer and the user's account.

Save to account uploads the added agents and the settings file, and, only if the user turned usage history
on, tokens used per day. Get from account replaces the two files here, keeps a `.before-sync` copy of each,
and never changes this computer's vault folder. Notes, keys and agent work never leave the computer.
"""

import json
import tomllib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core import added_agents
from core.account import Account
from core.settings import _replace_sections

USAGE_DAYS = 90


def usage_by_day(
    ledger: Path, days: int = USAGE_DAYS, now: datetime | None = None
) -> dict[str, int]:
    """Tokens per local day from usage.jsonl, for the last `days` days."""
    since = ((now or datetime.now().astimezone()) - timedelta(days=days)).date()
    totals: dict[str, int] = defaultdict(int)
    if not ledger.is_file():
        return {}
    for line in ledger.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            day = datetime.fromisoformat(row["ts"]).date()
            tokens = int(row["tokens"])
        except (ValueError, KeyError, TypeError):
            continue
        if day >= since and tokens > 0:
            totals[day.isoformat()] += tokens
    return dict(totals)


def save(account: Account, agents: Path, settings: Path, ledger: Path) -> dict[str, Any]:
    items = {"agents": json.dumps(added_agents.load(agents))}
    if settings.is_file():
        items["settings"] = settings.read_text(encoding="utf-8")
    account.sync_save(items)
    sent_usage = 0
    if account.consent()["usage"]:
        days = usage_by_day(ledger)
        account.usage_save(days)
        sent_usage = len(days)
    return {"saved": sorted(items), "usage_days": sent_usage}


def _vault_block(text: str) -> str:
    """The [vault] table of a settings file, as text, or nothing."""
    block: list[str] = []
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            inside = stripped == "[vault]"
        if inside:
            block.append(line)
    return "\n".join(block).strip()


def fetch(account: Account, agents: Path, settings: Path) -> dict[str, Any]:
    held = account.sync_fetch()
    if not held:
        raise ValueError(
            "Nothing is saved in your account yet. Use Save to account on the other computer."
        )
    got: list[str] = []
    if "agents" in held:
        incoming = json.loads(held["agents"]["body"])
        if agents.is_file():
            agents.with_name(agents.name + ".before-sync").write_bytes(agents.read_bytes())
        added_agents.save(agents, incoming)  # checks the shape before writing
        got.append("agents")
    if "settings" in held:
        incoming_text = held["settings"]["body"]
        tomllib.loads(incoming_text)  # refuse a file that does not parse
        here = settings.read_text(encoding="utf-8") if settings.is_file() else ""
        vault = _vault_block(here)
        merged = _replace_sections(incoming_text, ("[vault]",), [vault] if vault else [])
        tomllib.loads(merged)
        if settings.is_file():
            settings.with_name(settings.name + ".before-sync").write_text(here, encoding="utf-8")
        settings.parent.mkdir(parents=True, exist_ok=True)
        tmp = settings.with_suffix(".toml.tmp")
        tmp.write_text(merged, encoding="utf-8")
        tmp.replace(settings)
        got.append("settings")
    return {"fetched": got, "saved_at": max(h["updated_at"] for h in held.values())}
