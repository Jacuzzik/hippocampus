"""Token budgets and the network state."""

from dataclasses import asdict
from datetime import datetime
from typing import Any

from ai import network
from core import budget as budgets
from core.settings import (
    CAP_WINDOWS,
)


class BudgetPart:
    def budget_overrun(self) -> budgets.Overrun | None:
        return self.ledger.first_overrun(
            {
                "app": (self.settings.budget, None),
                "assistant": (self.settings.assistant_budget, "assistant"),
            }
        )

    def budget(self) -> dict[str, Any]:
        """Each cap, and the tokens used so far in each window, for the app and the assistant."""
        now = datetime.now().astimezone()
        scopes = {
            "app": (self.settings.budget, None),
            "assistant": (self.settings.assistant_budget, "assistant"),
        }
        used = {
            scope: {w: self.ledger.used(w, now, agent) for w in CAP_WINDOWS}
            for scope, (_caps, agent) in scopes.items()
        }
        caps = {scope: asdict(caps) for scope, (caps, _agent) in scopes.items()}
        return {"caps": caps, "used": used, "allowance": self.allowance}

    def budget_allow(self) -> dict[str, Any]:
        """Let the next request past a cap through, once."""
        self.allowance = True
        self.note("setting", text="one request allowed past a budget cap")
        return {"allowance": True}

    def network_state(self) -> dict[str, Any]:
        return {"mode": self.settings.network_mode, "modes": list(network.MODES)}
