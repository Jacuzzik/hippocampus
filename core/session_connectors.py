"""The Connectors page: one list of rows, checked with a time limit and remembered briefly,
so a service that is failing is not asked again in a tight loop."""

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from core import added_agents, connectors
from core import webhooks as webhook_store

# How long a checked answer is kept: a good one briefly, a failing one longer. "fresh" skips the wait,
# but never asks the same service twice within MIN_GAP seconds.
KEEP_GOOD_S = 15.0
KEEP_BAD_S = 60.0
MIN_GAP_S = 2.0


class ConnectorsPart:
    def _checked(
        self, ident: str, check: Callable[[], connectors.Row], fresh: bool
    ) -> tuple[connectors.Row, bool]:
        """The row for a service, from the short memory when it is recent. Also says whether a check ran."""
        cache: dict[str, tuple[float, connectors.Row]] = self.__dict__.setdefault(
            "_connector_cache", {}
        )
        known = cache.get(ident)
        if known is not None:
            age = time.monotonic() - known[0]
            keep = KEEP_BAD_S if known[1]["state"] in ("Error", "Not connected") else KEEP_GOOD_S
            if age < (MIN_GAP_S if fresh else keep):
                return known[1], False
        made = check()
        cache[ident] = (time.monotonic(), made)
        return made, True

    def connectors(self, request: dict[str, Any]) -> dict[str, Any]:
        fresh = request.get("fresh") is True
        agent_folders = [
            Path(a["folder"]) for a in added_agents.load(self.agents_path) if a.get("folder")
        ]
        folders = ([self.settings.vault] if self.settings.vault else []) + agent_folders
        host, model = self.settings.ollama_host, self.settings.ollama_model
        with ThreadPoolExecutor(max_workers=2) as pool:
            slow = {
                "ollama": pool.submit(
                    self._checked, "ollama", lambda: connectors.ollama(host, model), fresh
                ),
                "github": pool.submit(self._checked, "github", connectors.github, fresh),
            }
            local = [
                connectors.mcp(Path.home(), folders),
                connectors.webhooks(len(webhook_store.load(self.webhooks_path))),
                connectors.jobs(*self._job_counts()),
            ]
            results = {name: future.result() for name, future in slow.items()}
        checks = [
            ("ollama", "github")[i]
            for i, name in enumerate(("ollama", "github"))
            if results[name][1]
        ]
        if checks:
            # The activity log keeps who and when (you, now) and the outcome; never a token or a header.
            states = ", ".join(f"{name} {results[name][0]['state']}" for name in checks)
            self.note("setting", text=f"connectors checked by you: {states}")
        rows = [results["ollama"][0], results["github"][0], *local, *connectors.planned()]
        return {"connectors": rows}

    def _job_counts(self) -> tuple[int, int]:
        saved = self.jobs()["jobs"]
        return len(saved), sum(1 for j in saved if j.get("enabled"))
