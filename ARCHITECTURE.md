# How Hippocampus is built

Hippocampus is a desktop app: a notes vault with a graph, and real command-line agents that work on it.
It has three parts that run as separate processes.

## The three parts

| Part | Where | What it does |
|---|---|---|
| Window | `app/ui` (Svelte 5, TypeScript) | Everything you see: graph, note list, Control Room, agent cards, Settings. |
| Shell | `app/src-tauri` (Rust, Tauri) | Opens the window, starts the backend, and passes messages between the two. |
| Backend ("sidecar") | `core/`, `ai/`, `tools/` (Python) | Indexes the vault, runs the agents' programs, keeps settings, logs and messages. |

The window never talks to the network or the disk itself. It calls the backend through one command:
`invoke("sidecar_call", { method, params })`. The shell writes that as one JSON line to the backend's
input and reads the answer from its output. The backend also sends events the other way (for example
terminal output); the shell re-emits each as a `sidecar-event`.

## Backend

- `core/__main__.py` holds `Session`: one object per backend run. `Session.dispatch` maps a method name
  to a function. Methods that take no arguments are in the `simple` table, the others in `extra`.
- `core/vault/` reads the Markdown notes into a SQLite index (`data/storage/index`). `core/vault/changes.py`
  watches the vault folder, so the graph is rebuilt only after something changed.
- `core/terminal.py` starts each agent's command-line program in a pseudo-terminal and streams its
  output to the window. It also types lines into it (messages, the start-up inbox), one at a time.
- `core/sandbox.py` runs an agent's program inside bubblewrap when "Shell for every agent" is on.
- `core/inbox.py` is the message system between agents: one JSON file per message, in `~/.hippocampus/hive`.
- `core/briefing.py` holds the rules each agent starts with.
- `core/app_log.py` writes the backend log (`data/storage/logs/backend.log`), with keys masked.
- `ai/` talks to model providers and reads the agents' session files. `tools/` is the set of note tools
  an agent may call, and the small server (`tools/vault_mcp.py`) that offers them to Claude Code.

## Window

- `app/ui/App.svelte` lays out the regions. Each region sits inside an error boundary
  (`controls/PanelBoundary.svelte`), so one broken panel does not take the window down.
- `app/ui/regions/LiveTerminal.svelte` is the only terminal component. The main agent and every added
  agent use it.
- `app/ui/poll.ts` is the only place a repeating background read is set up. It pauses while the window
  is hidden.
- Colours, sizes and fonts come from `design/tokens.json`. `npm run tokens` writes `app/ui/styles/tokens.css`
  from it; nothing else may hard-code a colour (a test checks this).
- Shared controls live in `app/ui/controls/`: `Tabs`, `Dropdown`, `EmptyState`, `StatusCard`.

## Data on disk

| What | Where |
|---|---|
| Settings (no secrets) | `config/settings.toml` |
| API keys | the operating system's keychain |
| Note index, logs, error records, saved terminal screens | `data/storage/` |
| Agents' inboxes and outboxes | `~/.hippocampus/hive/<agent>/` |
| Agents' start-up inbox files | `~/.hippocampus/briefings/` |

## When the backend restarts

The shell starts the backend again if it stops. The agents' programs stop with it. Each answer to
`terminal_command` carries a `boot` id that changes on every backend start; when the window sees a new
id, each terminal starts its program again and the program resumes its last session.

## Checks

Run from the repository root unless noted. All of them must pass before a change is kept.

```
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
cd app && npm run format:check && npm run lint && npm run check && npm test
cd app && npx playwright test --workers=1      # needs the dev server on port 1420
```

Node 24 is required (`.nvmrc`). The browser tests use a pretend backend (`app/e2e/tauri-mock.ts`), so they
never touch real notes or agents. Python tests get their own hive folder (`tests/conftest.py`).
