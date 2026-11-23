"""The dashboards that read several sources: providers and models, money and spend, the vault, GitHub."""

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core import (
    added_agents,
    contract,
    github_repos,
    inbox,
    provider_usage,
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
        return {
            "plans": plans,
            "report": spend_plans.report(plans, usage, today),
            "providers": [{"id": p["id"], "name": p["name"]} for p in usage["providers"]],
            "currencies": list(spend_plans.CURRENCIES),
        }

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
