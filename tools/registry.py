"""A tool is a named action the model may ask for, with a safety tier.

Tiers: read and open run at once. write and act wait for the user's confirmation,
and the confirm card shows the exact change first.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

Tier = Literal["read", "open", "browse", "write", "act"]
CONFIRM_TIERS: frozenset[str] = frozenset({"write", "act"})


@dataclass(frozen=True)
class Tool:
    name: str
    tier: Tier
    description: str
    parameters: dict[str, Any]
    run: Callable[[dict[str, Any]], str]
    preview: Callable[[dict[str, Any]], str] | None = None


def needs_confirm(tier: str) -> bool:
    return tier in CONFIRM_TIERS
