"""Every task handed to an agent or a temp is a four-part contract (8.05): Objective, Output, Tools, Boundaries.

The same shape Munder Difflin's hive uses, so a task reads the same wherever it came from (Dispatch, a task
card's Temp button, a scheduled mission). A part left empty gets a plain default, so no task goes out vague.
"""

PARTS = ("Objective", "Output", "Tools", "Boundaries")
DEFAULTS = {
    "Output": "A short reply that says what you did and where the result is.",
    "Tools": "Whatever your rules allow. Read what already exists before you work it out again.",
    "Boundaries": "Only this task. Ask before anything outside it, then stop and report when it is done.",
}
PART_MAX = 4000


def is_contract(text: str) -> bool:
    """True when the text already has all four headings, so it is not wrapped twice."""
    return all(f"## {part}" in text for part in PARTS)


def build(parts: dict[str, object]) -> str:
    """The contract as markdown. Objective is required; the other parts fall back to DEFAULTS."""
    objective = str(parts.get("objective") or parts.get("Objective") or "").strip()
    if not objective:
        raise ValueError("A task needs an objective: say what should be done.")
    lines: list[str] = []
    for part in PARTS:
        value = str(parts.get(part.lower()) or parts.get(part) or "").strip() or DEFAULTS.get(
            part, ""
        )
        if len(value) > PART_MAX:
            raise ValueError(f"The {part.lower()} is longer than {PART_MAX} characters.")
        value = objective if part == "Objective" else value
        lines += [f"## {part}", value, ""]
    return "\n".join(lines).rstrip() + "\n"


def wrap(text: str) -> str:
    """A plain task as a contract, with the text as its objective. A contract is returned as it is."""
    return text if is_contract(text) else build({"objective": text})
