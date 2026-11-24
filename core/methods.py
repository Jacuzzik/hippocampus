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
    "note_history": _m("The kept earlier versions of a note, newest first (the last 20)."),
    "note_version": _m("The text of one kept version of a note."),
    "agent_worktree": _m(
        "Move an added agent into its own git worktree, or back to its folder.", _AGENT
    ),
    "mcp_servers": _m("The MCP servers in an added agent's own .mcp.json, secrets masked.", _AGENT),
    "mcp_add": _m("Add or replace an MCP server in an added agent's .mcp.json.", _AGENT),
    "mcp_remove": _m("Remove an MCP server from an added agent's .mcp.json.", _AGENT),
    "search_all": _m("Search notes, messages, tasks, calendar events and agents at once."),
    "playbooks": _m("Every playbook note in the vault's Playbooks folder, with its steps."),
    "playbook_run": _m(
        "Send a playbook's steps to an agent as one inbox message.",
        ("path", 'a playbook "path"'),
        ("agent", 'an "agent" id'),
    ),
    "handoff": _m(
        "Hand one agent's work to another: a note in Handoffs and an inbox message to the receiver.",
        ("from", 'a "from" agent id'),
        ("to", 'a "to" agent id'),
    ),
    "note_restore": _m("Put a kept version of a note back; the text it replaces is kept first."),
    # Account and keys
    "account": _m("Whether a Claude key is saved."),
    "user_account": _m(
        "The Hippocampus account: set up or not, signed in or not, name, plan, consent."
    ),
    "user_sign_in": _m("Start Google sign-in; gives the address to open in the browser."),
    "user_sign_in_cancel": _m("Stop waiting for the browser sign-in."),
    "user_sign_out": _m("Sign out and delete the saved sign-in from the keychain."),
    "user_delete": _m("Delete the Hippocampus account on the service, then sign out."),
    "user_consent": _m("Save the sync and usage-history choices (both off by default)."),
    "user_sync_save": _m(
        "Upload the added agents and settings (and usage per day, if on) to the account."
    ),
    "user_sync_fetch": _m("Replace the added agents and settings here with the account's copy."),
    "user_shares": _m("The account's share links."),
    "user_share_delete": _m("Delete one share link.", ("id", 'the link "id"')),
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
    "save_export": _m(
        "Save a text file into the exports folder.",
        ("name", 'a file "name"'),
        ("text", 'the "text"'),
    ),
    "export_notes": _m("Zip the notes of the open vault into the exports folder."),
    "cards": _m("The agent cards."),
    "card_from_note": _m("Make a card from text selected in a note, with a link back."),
    "card_note": _m("Make or update a card's own note page in the vault's Cards folder."),
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
    "apps": _m("The catalogue of apps a dashboard can be made from, and which are connected."),
    "app_connect": _m("Save an app's key in the keychain.", ("id", 'an app "id"')),
    "app_disconnect": _m("Remove an app's key.", ("id", 'an app "id"')),
    "app_board": _m("The numbers of one connected app.", ("id", 'an app "id"')),
    "mail_status": _m("Whether Gmail is connected for receipts, and the last scan."),
    "mail_connect": _m(
        "Connect Gmail with an app password and scan its receipts.",
        ("email", "the Gmail address"),
        ("password", "an app password"),
    ),
    "mail_disconnect": _m("Forget the Gmail address and its app password."),
    "mail_scan": _m("Read the receipts again: subscriptions, purchases, sales and refunds."),
    "purchases_import": _m(
        "Read purchases and subscriptions from a downloaded file (Google Takeout, Apple data"
        " copy, bank statement).",
        ("name", "the file name"),
        ("data", "the file, base64"),
    ),
    "purchases_remove": _m("Forget an added file's purchases.", ("name", "the file name")),
    "update_state": _m("Whether the update check is on, and what it last found."),
    "update_set": _m("Turn the update check on or off."),
    "update_check": _m("Ask GitHub for the newest release and its notes."),
    "calendar_link_state": _m(
        "Whether a calendar's private iCal address is connected, and its events."
    ),
    "calendar_link_set": _m(
        "Connect a calendar by its private iCal address.", ("url", "the calendar's iCal address")
    ),
    "calendar_link_clear": _m("Forget the calendar's address."),
    "calendar_read": _m("Read the connected calendar again."),
    "notion_state": _m("Whether Notion is connected."),
    "notion_connect": _m(
        "Connect Notion with an integration secret.", ("token", "the integration secret")
    ),
    "notion_disconnect": _m("Forget the Notion secret."),
    "notion_search": _m("Find Notion pages and databases shared with the integration."),
    "notion_import": _m(
        "Read one Notion page or database into a vault note.", ("id", "a Notion page id")
    ),
    "semantic_state": _m("How many notes the meaning index holds."),
    "semantic_build": _m("Build or refresh the meaning index with the local embedding model."),
    "semantic_search": _m("Find notes by meaning.", ("query", "what to look for")),
    "plugin_list": _m("The installed plugins."),
    "plugin_install": _m(
        "Install a plugin from a .zip.", ("name", "the file name"), ("data", "the file, base64")
    ),
    "plugin_enable": _m("Switch a plugin on or off for every agent.", ("name", "a plugin name")),
    "plugin_remove": _m("Remove an installed plugin.", ("name", "a plugin name")),
    "briefing_build": _m(
        "The exact briefing an agent starts with, block by block, and its size.", _AGENT
    ),
    "briefing_blocks_set": _m("Turn an optional briefing block on or off for every agent."),
    "trail_notes": _m("Each agent's newest trail note, so a missing one shows."),
    "capture": _m(
        "Keep a quick thought in the vault's Inbox note, stamped with the time and agent.",
        ("text", "the thought"),
    ),
    "demo_state": _m("Whether the sample vault is open, and where to go back to."),
    "demo_open": _m(
        "Write the labelled sample vault and open it; the user's own vault is untouched."
    ),
    "demo_leave": _m("Go back to the vault that was open before the sample vault."),
    "usage_stats": _m("Counts read from the local activity log. Nothing is sent anywhere."),
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
    "share": _m(
        "A password link to one note, on the account.",
        ("path", 'the note "path"'),
        ("password", 'a "password" of 8 or more characters'),
    ),
    # Agents and their folders
    "agents": _m("The added agents."),
    "save_agents": _m("Save the added agents."),
    "workspaces": _m("Folders an agent can work in."),
    "create_workspace": _m("Make a folder for an agent."),
    "agent_session": _m("Prepare an agent's folder and session.", _AGENT),
    "git_status": _m("Short git status of an agent's folder."),
    "open_folder": _m("Open an agent's folder in the file manager or VS Code."),
    "issues": _m("Open GitHub issues of a folder."),
    "ci": _m("The newest CI run of a folder's repo."),
    "github_board": _m("Open pull requests, issues and CI runs of one GitHub repository."),
    "phone_status": _m("Android devices seen by adb, and which are being mirrored."),
    "phone_mirror": _m("Mirror a phone's screen in a scrcpy window, after approval."),
    "phone_view": _m("Show a phone's screen inside the app (view only), after approval."),
    "phone_stop": _m("Stop mirroring a phone, in the app and in its own window."),
    "phone_control": _m("Tap, swipe, press a key or type on a phone, after approval."),
    "tokens": _m("This month's token use per folder."),
    # Terminals
    "terminal_start": _m("Start an agent's program.", _AGENT),
    "terminal_input": _m("Send keys to an agent's program.", _AGENT),
    "terminal_resize": _m("Tell an agent's program its new size.", _AGENT),
    "terminal_stop": _m("Stop an agent's program.", _AGENT),
    "remote_status": _m("Whether an agent's remote control is connected, and its link.", _AGENT),
    "terminal_context": _m("How full an agent's context is.", _AGENT),
    "terminal_traces": _m("What an agent ran.", _AGENT),
    "terminal_rebrief": _m("Point a running agent at its briefing again.", _AGENT),
    "briefing_preview": _m("The briefing a new agent would start with."),
    "agent_pins": _m("The notes pinned to an agent, with their token cost.", _AGENT),
    "terminal_command": _m("An agent's running command and the backend's boot stamp."),
    # Jobs, helpers, webhooks
    "jobs": _m("Scheduled jobs."),
    "set_job": _m("Turn a scheduled job on or off."),
    "missions": _m("Scheduled missions: messages sent to an agent on a schedule."),
    "mission_save": _m("Add or change a scheduled mission."),
    "mission_remove": _m("Remove a scheduled mission.", ("id", 'a mission "id"')),
    "run_job": _m("Run a scheduled job now."),
    "provider_usage": _m("Tokens used per provider and model, from each AI tool's own logs."),
    "finance": _m("What AI costs each month, from the plans and prices you enter."),
    "finance_save": _m("Save your AI plans and prices."),
    "open_link": _m("Open an https page in the browser."),
    "vault_board": _m("Counts about the vault, and the main agent's summary of it."),
    "vault_insights_request": _m("Ask the main agent to write the vault summary."),
    "github_all": _m("Every GitHub repository you have, and what the agents did in each."),
    "calendar": _m("One month of your events and the days scheduled jobs will run."),
    "calendar_add": _m("Add an event to the calendar."),
    "calendar_remove": _m("Remove an event from the calendar."),
    "calendar_mark": _m("Mark a calendar event done or failed, or schedule it again."),
    "helpers": _m("Short-lived helper jobs."),
    "start_helper": _m("Start a helper job."),
    "breakers": _m(
        "The circuit breaker's last check of each agent: healthy, warn or tripped, and why."
    ),
    "fleet": _m("Every agent's status, model, context use and inbox backlog, as in fleet.json."),
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
