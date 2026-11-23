"""The dashboards that read several sources: providers and models, money and spend, the vault, GitHub."""

import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from core import (
    added_agents,
    contract,
    github_repos,
    inbox,
    mail_receipts,
    provider_usage,
    spend_auto,
    spend_plans,
    vault_board,
)


class BoardsPart:
    @property
    def spend_plans_path(self) -> Path:
        return self.storage / "spend_plans.json"

    @property
    def vault_insights_path(self) -> Path:
        return self.storage / "vault_insights.json"

    def provider_usage(self) -> dict[str, Any]:
        return provider_usage.report(self.storage)

    def finance(self, request: dict[str, Any] | None = None) -> dict[str, Any]:
        today = datetime.now().astimezone().date()
        plans = spend_plans.load(self.spend_plans_path)
        usage = provider_usage.report(self.storage, today=today)
        # What was found in receipts and added files fills the board beside the user's own rows.
        events = self.found_events()
        found_subs = mail_receipts.summarise(events, today)["subscriptions"] if events else []
        merged = spend_auto.fill(
            plans, found_subs, events, fresh=not self.spend_plans_path.exists()
        )
        report = spend_plans.report(merged, usage, today)
        report["wallets"] = spend_auto.wallets(merged, report["subs"], events, found_subs, today)
        report["history"] = spend_auto.history(events, merged["currency"], today)
        report["found"] = len(events)
        return {
            "plans": {**plans, "currency": merged["currency"]},
            "report": report,
            "providers": [{"id": p["id"], "name": p["name"]} for p in usage["providers"]],
            "currencies": list(spend_plans.CURRENCIES),
        }

    def open_link(self, request: dict[str, Any]) -> dict[str, Any]:
        """Opens an https page in the user's browser (a subscription's manage or renew page)."""
        link = spend_plans._link(request.get("url"))
        if not link:
            raise ValueError("No link to open.")
        webbrowser.open(link)
        return {"opened": link}

    def finance_save(self, request: dict[str, Any]) -> dict[str, Any]:
        spend_plans.save(self.spend_plans_path, request.get("plans"))
        return self.finance()

    def vault_board(self) -> dict[str, Any]:
        with self.lock:
            if self.indexer is None:
                raise ValueError("no vault is open")
            store = self.indexer.store
            graph = store.graph()
            mtimes = {path: state.mtime_ns for path, state in store.note_states().items()}
            broken = sum(
                1 for path in mtimes for _raw, target in store.outgoing(path) if target is None
            )
        return {
            "stats": vault_board.stats(graph, mtimes, broken, time.time_ns()),
            "insights": vault_board.load_insights(self.vault_insights_path),
        }

    def vault_insights_request(self) -> dict[str, Any]:
        """Ask the main agent to write the vault summary. The click on the dashboard is the request."""
        objective, output = vault_board.request_text(self.vault_insights_path)
        inbox.send(
            self.hive_path,
            inbox.USER,
            "hippoherman",
            "Vault summary for the dashboard",
            contract.build({"objective": objective, "output": output}),
            act="request",
            work="vault-summary",
        )
        self.changed("inbox")
        return {"sent": True, **self.vault_board()}

    def github_all(self) -> dict[str, Any]:
        agents: list[tuple[str, str, Path]] = []
        if self.settings.vault:
            agents.append(("hippoherman", "Hippoherman", Path(str(self.settings.vault))))
        for row in added_agents.load(self.agents_path):
            folder = row.get("cwd") or row.get("folder")
            if row.get("id") and folder:
                agents.append(
                    (str(row["id"]), str(row.get("name") or row["id"]), Path(str(folder)))
                )
        return github_repos.board(agents)
