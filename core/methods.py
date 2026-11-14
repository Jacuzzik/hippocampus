"""Every method the window can call on the backend: its name, the keys it needs and one line of help.

`Session.dispatch` refuses a name that is not here and a call that lacks a key named here, with a plain
sentence. A test checks that this table and the handlers in `core/session_dispatch.py` list the same names.
"""

from dataclasses import dataclass
from typing import Any

# The words used for a missing key, so each sentence reads the way the window shows it.
AGENT = 'an "agent" id'


@dataclass(frozen=True)
class Method:
    text: str
    # key in the request -> the words for it in the "needs" sentence; each must be a non-empty string.
    needs: tuple[tuple[str, str], ...] = ()


def _m(text: str, *needs: tuple[str, str]) -> Method:
    return Method(text, needs)


_AGENT = ("agent", AGENT)

METHODS: dict[str, Method] = {
    # Notes and the graph
    "graph": _m("The notes and links, for the graph."),
    "open": _m("Open a vault folder.", ("vault", 'a "vault" folder path')),
    "read": _m("Read one note by its id."),
    "note_text": _m("The text of a note."),
    "note_save": _m("Save a note."),
    "note_delete": _m("Delete a note."),
    "note_colour": _m("Colour a note through its tags."),
    # Account and keys
    "account": _m("Whether a Claude key is saved."),
    "sign_in": _m("Save the Claude key in the keychain."),
    "sign_out": _m("Remove the Claude key."),
    "remove_data": _m("Delete the index cache and the key; never the vault."),
    "keys": _m("Which provider keys are saved (last four characters only)."),
    "save_key": _m("Save one provider key."),
    "clear_key": _m("Remove one provider key."),
    # Chat and tools
    "chat": _m("Send a message to the assistant."),
    "confirm": _m("Approve or refuse a pending tool call."),
    "answer": _m("Answer a question the assistant asked."),
    "asks": _m("Questions waiting for an answer."),
    "tools": _m("The assistant's tools and which are allowed."),
    "set_tools": _m("Choose the allowed tools."),
    "stop": _m("The kill switch: stop every pending tool call."),
    "chat_history": _m("Saved chat sessions of an agent.", _AGENT),
    "chat_history_save": _m("Save an agent's chat sessions.", _AGENT),
    "current_session": _m("An agent's current session id.", _AGENT),
    "new_session": _m("Start a new session for an agent.", _AGENT),
    # Tasks, cards and the inbox
    "tasks": _m("The office task board."),
    "activity": _m("The tool log and office events."),
    "clear_activity": _m("Empty the tool log and office events."),
    "cards": _m("The agent cards."),
    "card_create": _m("Add a card."),
    "card_update": _m("Change a card."),
    "inbox": _m("The inbox messages."),
    "inbox_search": _m("Search the inbox."),
    "inbox_thread": _m("One inbox conversation."),
    "task_send": _m("Send a task message to an agent."),
    # Settings
    "settings": _m("The settings the Settings pages show, and the schema of every key."),
    "settings_export": _m("Settings as text, without keys."),
    "settings_import": _m("Apply exported settings."),
    "set_vault": _m("Change the vault folder."),
    "set_network": _m("Change the network mode."),
    "network": _m("The network mode."),
    "set_budget": _m("Change the token budgets."),
    "budget": _m("Token use against the budgets."),
    "budget_allow": _m("Let a paused budget continue."),
    "set_agent_shell": _m("Turn the fenced shell for every agent on or off."),
    "set_number": _m(
        "Change one whole-number setting.",
        ("key", 'the "key" of a setting'),
    ),
    "set_engine": _m("Choose the main agent's provider and model."),
    "engine": _m("The main agent's provider and model."),
    "provider_status": _m("Which providers are usable here."),
    "local_status": _m("Whether the local model server answers."),
    "connectors": _m("Every connector as a row: state, reason and what it needs."),
    "doctor": _m("Health checks with what to do about each gap."),
    "link_doctor": _m("Broken links and notes with no links."),
    "logs": _m("The newest lines of the backend log."),
    "crashes": _m("Recent error records."),
    "clear_crashes": _m("Delete the error records."),
    "record_crash": _m("Write an error record from the window."),
    "system": _m("Memory and disk use."),
    # Memory, skills, sharing
    "memory": _m("Agents' memory notes with sizes."),
    "memory_status": _m("Whether meaning search is set up."),
    "memory_search": _m("Search memory notes."),
    "skills": _m("Installed skills."),
    "remove_skill": _m("Remove a skill."),
    "install_skill": _m("Install a skill from a folder."),
    "open_skill_folder": _m("Open the skills folder."),
    "share": _m("Share a note."),
    # Agents and their folders
    "agents": _m("The added agents."),
    "save_agents": _m("Save the added agents."),
    "workspaces": _m("Folders an agent can work in."),
    "create_workspace": _m("Make a folder for an agent."),
    "agent_session": _m("Prepare an agent's folder and session.", _AGENT),
    "git_status": _m("Short git status of an agent's folder."),
    "open_folder": _m("Open an agent's folder in the file manager or VS Code."),
    "issues": _m("Open GitHub issues of a folder."),
    "tokens": _m("This month's token use per folder."),
    # Terminals
    "terminal_start": _m("Start an agent's program.", _AGENT),
    "terminal_input": _m("Send keys to an agent's program.", _AGENT),
    "terminal_resize": _m("Tell an agent's program its new size.", _AGENT),
    "terminal_stop": _m("Stop an agent's program.", _AGENT),
    "terminal_context": _m("How full an agent's context is.", _AGENT),
    "terminal_traces": _m("What an agent ran.", _AGENT),
    "terminal_command": _m("An agent's running command and the backend's boot stamp."),
    # Jobs, helpers, webhooks
    "jobs": _m("Scheduled jobs."),
    "set_job": _m("Turn a scheduled job on or off."),
    "helpers": _m("Short-lived helper jobs."),
    "start_helper": _m("Start a helper job."),
    "watchers": _m("Folder watchers."),
    "webhooks": _m("Saved webhooks."),
    "save_webhook": _m("Add a webhook."),
    "delete_webhook": _m("Remove a webhook."),
    "run_webhook": _m("Run a webhook once."),
}


def check(request: dict[str, Any]) -> str:
    """Returns the method name, or raises ValueError for an unknown method or a missing key."""
    name = request.get("method")
    spec = METHODS.get(name) if isinstance(name, str) else None
    if spec is None:
        raise ValueError(f"unknown method: {name!r}")
    for key, words in spec.needs:
        value = request.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f'"{name}" needs {words}')
    return str(name)
