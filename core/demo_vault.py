"""N.26: a small sample vault, clearly labelled, with enough links to make the graph worth looking at.

It is written into the app's storage folder, never into the user's own vault. Opening it is a vault switch the
user can undo with "Back to my vault"."""

from pathlib import Path

from core import safe_write

FOLDER = "demo-vault"
LABEL = "Demo vault: sample notes made by Hippocampus. Nothing here is yours."

NOTES: dict[str, str] = {
    "Start here.md": f"""# Start here

> {LABEL}

Welcome. This is a sample brain so the graph has something to show.

- Every [[Ideas]] note links to the notes it came from.
- [[Projects]] lists what is in flight; each project has its own note.
- [[People]] and [[Reading list]] show how links turn a pile of notes into a map.
- Agents read and write notes like these. See [[How agents help]].

#demo
""",
    "Ideas.md": """# Ideas

Loose thoughts that may become projects. #demo #ideas

- [[Garden planner]]: a calendar of what to plant and when.
- [[Trip to Lisbon]]: dates, flights and a list of places.
- [[Learning Spanish]]: twenty minutes a day, tracked in [[Daily notes]].
- Read about [[Spaced repetition]].
""",
    "Projects.md": """# Projects

What is in flight. #demo #projects

- [[Garden planner]] (idea, not started)
- [[Trip to Lisbon]] (booking)
- [[Learning Spanish]] (daily)

Back to [[Start here]].
""",
    "Garden planner.md": """# Garden planner

A planting calendar. #demo #projects

Ask [[Maria Silva]] which tomatoes grow well here. Keep results in [[Daily notes]].
See [[Ideas]] and [[Projects]].
""",
    "Trip to Lisbon.md": """# Trip to Lisbon

#demo #travel

- Flights: book by the end of the month.
- Meet [[Maria Silva]] for lunch.
- Read [[The Pragmatic Programmer]] on the plane.

Part of [[Projects]].
""",
    "Learning Spanish.md": """# Learning Spanish

#demo #learning

Twenty minutes a day. Use [[Spaced repetition]] for vocabulary.
Practise with [[Maria Silva]]. Log each day in [[Daily notes]].
""",
    "Spaced repetition.md": """# Spaced repetition

#demo #learning

Review a card just before you would forget it. Used in [[Learning Spanish]].
Related reading: [[Reading list]].
""",
    "Daily notes.md": """# Daily notes

#demo #journal

One line a day. Today: tried [[Spaced repetition]] cards for [[Learning Spanish]].
Quick thoughts also land in the Inbox note (Ctrl+Shift+Space).
""",
    "People.md": """# People

#demo #people

- [[Maria Silva]]: friend in Lisbon, gardener.
- [[Dev Patel]]: colleague, writes the weekly summary.
""",
    "Maria Silva.md": """# Maria Silva

#demo #people

Lives in Lisbon. Helps with the [[Garden planner]], meets for the [[Trip to Lisbon]],
and speaks Spanish for [[Learning Spanish]]. Listed in [[People]].
""",
    "Dev Patel.md": """# Dev Patel

#demo #people

Writes the weekly summary. See [[How agents help]] for how an agent drafts it. Listed in [[People]].
""",
    "Reading list.md": """# Reading list

#demo #reading

- [[The Pragmatic Programmer]]
- Notes on [[Spaced repetition]]
""",
    "The Pragmatic Programmer.md": """# The Pragmatic Programmer

#demo #reading

Small steps, honest estimates. Packed for the [[Trip to Lisbon]]. On the [[Reading list]].
""",
    "How agents help.md": """# How agents help

#demo #agents

Agents read notes like these and write their own. Each one leaves a trail note
and a handoff so the next session knows where it stopped.

- Ask an agent to tidy [[Daily notes]].
- Ask one to draft the weekly summary for [[Dev Patel]].
- Open [[Start here]] to begin again.
""",
}


def build(storage: Path) -> Path:
    """Write the sample notes (never over a note the user has since changed) and return the folder."""
    folder = storage / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in NOTES.items():
        target = folder / name
        if not target.exists():
            safe_write.write_text(target, text)
    return folder


def is_demo(storage: Path, vault: Path | None) -> bool:
    return vault is not None and vault.resolve() == (storage / FOLDER).resolve()
