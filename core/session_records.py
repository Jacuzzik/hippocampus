"""Records the app keeps on this computer: the crash list, the backend log and the saved webhooks."""

from pathlib import Path
from typing import Any

from core import (
    app_log,
    crash_log,
    webhooks,
)


class RecordsPart:
    def crashes(self) -> dict[str, Any]:
        """The newest error records kept on disk (UI errors and unhandled backend thread errors)."""
        return {"crashes": crash_log.recent(self.storage)}

    def record_crash(self, request: dict[str, Any]) -> dict[str, Any]:
        crash_log.record(
            self.storage, request.get("source"), request.get("message"), request.get("at")
        )
        return {"ok": True}

    def clear_crashes(self) -> dict[str, Any]:
        crash_log.clear(self.storage)
        return self.crashes()

    def logs(self, request: dict[str, Any]) -> dict[str, Any]:
        """The newest lines of the backend log file, for Settings > Advanced. Keys are masked when written."""
        limit = request.get("limit", 200)
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be a whole number")
        return {"path": str(app_log.path(self.storage)), "lines": app_log.tail(self.storage, limit)}

    def webhooks_state(self) -> dict[str, Any]:
        return {"webhooks": webhooks.load(self.webhooks_path)}

    def save_webhook(self, request: dict[str, Any]) -> dict[str, Any]:
        hooks = webhooks.add(
            webhooks.load(self.webhooks_path), request.get("name"), request.get("kind")
        )
        webhooks.save(self.webhooks_path, hooks)
        return self.webhooks_state()

    def delete_webhook(self, request: dict[str, Any]) -> dict[str, Any]:
        hook_id = request.get("id")
        if not isinstance(hook_id, str):
            raise ValueError('"delete_webhook" needs an "id"')
        kept = webhooks.remove(webhooks.load(self.webhooks_path), hook_id)
        webhooks.save(self.webhooks_path, kept)
        return self.webhooks_state()

    def run_webhook(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("approve") is not True:
            raise ValueError("running a webhook needs the user's approval")
        hook = webhooks.find(webhooks.load(self.webhooks_path), request.get("id"))
        kinds = {"link_check": self._link_check}
        run = kinds.get(hook.get("kind"))
        if run is None:
            raise ValueError(
                f"This webhook has the kind {hook.get('kind')!r}, which this app cannot run. "
                f"It can run: {', '.join(kinds)}."
            )
        result = run()
        self.note("approval", tool="run_webhook", tier="act", approved=True, by="card")
        self.note("handoff", text=result)
        return {"result": result}

    @property
    def webhooks_path(self) -> Path:
        return self.storage / "webhooks.json"
