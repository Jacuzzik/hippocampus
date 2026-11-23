"""The circuit breaker (7.21): watches each running agent for a loop, a run of failures, a full context
or repeated crashes, and steers it once instead of letting it spend tokens going round.

`assess` is a pure function of what the app can already see: the agent's recent tool calls (newest
first, from its session file), its context use and its recent crashes. It answers a level, "healthy",
"warn" or "tripped", and the reasons. On a trip the session types one plain steer line into the
agent's terminal (a /compact for a full context), at most once per COOLDOWN per reason, and writes
it to the activity log. The kill switch and the budgets stay the hard stops; this only steers.
"""

from datetime import UTC, datetime
from typing import Any

REPEAT_WARN = 3  # the same call this many times in a row
REPEAT_TRIP = 5
FAIL_WINDOW = 8  # of the newest calls...
FAIL_TRIP = 6  # ...this many failed
CONTEXT_WARN = 80
CONTEXT_TRIP = 92
CRASH_WINDOW_S = 15 * 60
CRASH_TRIP = 3
COOLDOWN_S = 10 * 60

STEER = {
    "looping": (
        "Circuit breaker: you have made the same call {n} times in a row. Stop repeating it. Write"
        " down what you tried and what happened, then try a different approach or ask for help."
    ),
    "failing": (
        "Circuit breaker: {n} of your last {window} tool calls failed. Stop and read the errors,"
        " say in one line what is going wrong, then change approach instead of retrying."
    ),
}


def _same_run(trace: list[dict[str, Any]]) -> int:
    """How many of the newest calls are the same tool with the same input."""
    if not trace:
        return 0
    first = (trace[0].get("tool"), trace[0].get("detail"))
    run = 0
    for call in trace:
        if (call.get("tool"), call.get("detail")) != first:
            break
        run += 1
    return run


def _crashes(rows: list[dict[str, Any]], agent: str, now: datetime) -> int:
    count = 0
    for row in rows:
        if row.get("source") != f"agent {agent}":
            continue
        try:
            at = datetime.fromisoformat(str(row.get("at")))
        except ValueError:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        if (now - at).total_seconds() <= CRASH_WINDOW_S:
            count += 1
    return count


def assess(
    agent: str,
    trace: list[dict[str, Any]],
    context: int | None,
    crash_rows: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    reasons: list[dict[str, Any]] = []
    level = "healthy"

    def add(kind: str, tripped: bool, text: str, **extra: int) -> None:
        nonlocal level
        reasons.append({"kind": kind, "tripped": tripped, "text": text, **extra})
        if tripped:
            level = "tripped"
        elif level == "healthy":
            level = "warn"

    run = _same_run(trace)
    if run >= REPEAT_WARN:
        add("looping", run >= REPEAT_TRIP, f"The same call {run} times in a row.", n=run)
    recent = trace[:FAIL_WINDOW]
    failed = sum(1 for call in recent if call.get("status") == "failed")
    if len(recent) >= FAIL_TRIP and failed >= FAIL_TRIP:
        add(
            "failing",
            True,
            f"{failed} of the last {len(recent)} calls failed.",
            n=failed,
            window=len(recent),
        )
    if context is not None and context >= CONTEXT_WARN:
        add("context", context >= CONTEXT_TRIP, f"Context is {context}% full.", n=context)
    crashes = _crashes(crash_rows, agent, now)
    if crashes >= CRASH_TRIP:
        add("crashing", True, f"It crashed {crashes} times in 15 minutes.", n=crashes)
    return {"agent": agent, "level": level, "reasons": reasons}


def steer_text(reason: dict[str, Any], compact_prompt: str) -> str | None:
    """The one line typed into the agent's terminal for a tripped reason, or None for a reason the
    agent cannot fix by itself (crashes are for the user, on the Monitor tab)."""
    if not reason.get("tripped"):
        return None
    if reason["kind"] == "context":
        return compact_prompt
    template = STEER.get(reason["kind"])
    return template.format(**reason) if template else None
