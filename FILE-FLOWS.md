# What happens: main flows in Hippocampus

Checked by reading these files: `core/terminal.py`, `ai/cli_sessions.py`, `app/ui/owner/AgentBar.svelte`, `core/__main__.py` (parts). Flows marked "not read" are not verified.

## 1. Agent terminal starts
1. The card's terminal button calls the sidecar method `terminal_start` (through `app/src-tauri/src/sidecar.rs`).
2. `core/terminal.py` `Terminals.start()` picks the CLI from `CLI_FOR` (claude, codex, ollama, agy).
3. For Claude, `_command()` uses `--resume` if a saved session exists, else `--session-id`. It adds the briefing file, vault tools, and a deny list for reading or editing the app's own folder. The main agent (hippo) gets a fenced shell; normal agents get no shell.
4. The CLI runs in a pseudo-terminal (PTY). `_pump()` streams its output to the app and keeps the last 200 KB so a reopened terminal shows the screen.

## 2. Card values refresh (every 3 seconds)
1. `AgentBar.svelte` `refreshLive()` calls `terminal_command` and, when a command runs, `terminal_context` for the main agent and each added agent.
2. `terminal.py` `info()` returns the command, status (Working or Idle), the running and last tool calls, and the model.
3. `ai/cli_sessions.py` reads the agent's Claude Code transcript (`~/.claude/projects/*/<session>.jsonl`):
   - `open_tool_calls` and `last_tool_call` give CMD;
   - `last_model` gives MODEL (new, not yet checked on screen);
   - `context_percent` gives CTX.
4. Status is Working when a tool call is open or output came in the last 10 seconds; otherwise Idle.
5. Provider name and logo come from the running CLI name (`CLI_LABEL`, `CLI_ID`) and fall back to the agent's saved provider.

## 3. Chat (not read)
Chat goes through `ai/router.py` to a provider in `ai/providers/`. Not verified.

## 4. Vault index (not read)
`core/vault/watcher.py` watches the vault; `indexer.py` and `parser.py` update the index in `store.py`. Not verified.

## 5. Startup (partly read)
The Tauri shell (`app/src-tauri/src/`) starts the Python sidecar (`core/__main__.py`). The UI (`app/ui/main.ts`, `App.svelte`) then loads. Partly verified only.

## Known gaps
- Most files were not read line by line. `FILE-DOCS.md` gives purpose lines only for 99 of 158 files.
- Four files are tracked in git but missing from disk.
