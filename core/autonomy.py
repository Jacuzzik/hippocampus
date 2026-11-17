"""How far an agent may act without asking (7.20), turned into each CLI's own permission flags.

Three levels, saved per agent as "autonomy":
  ask   - the CLI asks before it edits a file or runs a command (the CLI's own default);
  edits - file edits go through without asking; commands still ask;
  full  - edits and commands go through without asking.

The app's folder stays protected at every level: an agent whose folder is inside the app always asks,
and "full" needs a fence that keeps the app read-only (the sandbox, or Codex's own workspace sandbox).
Without one, "full" runs as "edits". The level actually used is shown on the agent's panel.
"""

LEVELS = ("ask", "edits", "full")
DEFAULT = "edits"
LABELS = {
    "ask": "Ask first",
    "edits": "Edit freely, ask before commands",
    "full": "Act without asking",
}

# Checked against each CLI's --help on 2026-11-17. Claude Code's "full" allows the shell and the web
# instead of using bypassPermissions, whose first-run warning would stop an agent's terminal.
_FLAGS: dict[str, dict[str, list[str]]] = {
    "claude": {
        "ask": [],
        "edits": ["--permission-mode", "acceptEdits"],
        "full": ["--permission-mode", "acceptEdits"],
    },
    "codex": {
        "ask": ["--ask-for-approval", "on-request"],
        "edits": ["--sandbox", "workspace-write", "--ask-for-approval", "on-request"],
        "full": ["--sandbox", "workspace-write", "--ask-for-approval", "never"],
    },
    "gemini-cli": {
        "ask": [],
        "edits": ["--approval-mode", "auto_edit"],
        "full": ["--approval-mode", "yolo"],
    },
    "antigravity": {
        "ask": [],
        "edits": ["--mode", "accept-edits"],
        "full": ["--dangerously-skip-permissions"],
    },
}
# The tools Claude Code runs without asking at "full". Its deny rules (the app folder, the fenced shell) still win.
CLAUDE_FULL_TOOLS = ("Bash", "WebFetch", "WebSearch")


def level_for(value: object) -> str:
    return value if isinstance(value, str) and value in LEVELS else DEFAULT


def effective(provider: str, value: object, *, sandboxed: bool, folder_in_app: bool) -> str:
    """The level that really applies, after the app folder's protection."""
    level = level_for(value)
    if folder_in_app:
        return "ask"
    if level == "full" and not (sandboxed or provider == "codex"):
        return "edits"
    return level


def flags(provider: str, level: str) -> list[str]:
    """The CLI flags for a level. A program with no permission flags (Ollama, OpenCode, a custom command) gets none."""
    return list(_FLAGS.get(provider, {}).get(level, []))


def describe(provider: str, asked: object, used: str) -> str:
    """One line for the agent's panel: the level in use, and why it differs from the one picked."""
    if provider not in _FLAGS:
        return "Autonomy: set by the program itself"
    text = f"Autonomy: {LABELS[used]}"
    if used != level_for(asked):
        text += f" (picked {LABELS[level_for(asked)]}; limited to keep the app folder safe)"
    return text
