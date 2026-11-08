# Hippocampus: whole system plan

Status as of 2026-11-08 18:08 UTC. Written for Thalha and for any agent that starts work on Hippocampus.

## 1. What the system is

- A desktop app (Tauri shell, Svelte UI in `app/ui`) with a Python helper (`core/`, started as `python -m core serve`).
- The app runs a set of agents. The **main agent** is Hippoherman, the boss. Every other agent is a **normal agent** with its own name, job and goal.
- Each agent runs in a terminal inside the app. The terminal runs one CLI: Claude Code, Codex, Gemini CLI, Antigravity, Ollama, or OpenCode (which runs the API providers).
- Agents message each other through an inbox and outbox kept in `data/storage/hive/<agent>/`.

## 2. Providers (14)

Claude, Codex, Gemini CLI, Antigravity, Ollama, OpenAI, xAI, Moonshot, Gemini, Qwen, DeepSeek, Mistral, Groq, OpenRouter.

- Claude runs through Claude Code. Its chat is resumed by session id.
- Codex, Gemini CLI, Antigravity and the OpenCode providers run as their own CLIs.
- Ollama runs `ollama run`. It keeps no chat between starts, so it cannot resume.
- vLLM and LM Studio are paused by Thalha, so they are out of the count.

Source of truth: `ENGINE_PROVIDERS` in `core/settings.py`, `CLI_FOR` and `OPENCODE_FOR` in `core/terminal.py`.

## 3. Briefings (what each agent is told)

- **Main agent** gets the main briefing (its role, the rules for all agents, the vault rules, the reply rules).
- **Normal agent** gets its own briefing: the same rules, plus its name, job and goal.
- The briefing is written to `data/storage/briefings/<agent>.md` on every start.
- The app then points the agent at that file. Claude gets it as a start flag. Other CLIs get a pointer message.
  - OpenCode: the pointer is its first prompt, passed at launch (`--prompt`). Thalha confirmed OpenCode received its briefing (18:04 WhatsApp).
  - Other CLIs: the pointer is typed 6 seconds after the CLI starts (`BRIEFING_DELAY_S`). **Not yet confirmed working for these** — see open items.

## 4. Session history (resume)

- Claude: resumed with `--resume <id>` when its transcript exists.
- Codex: `codex resume --last` in the agent's folder.
- Gemini CLI: `--resume latest`.
- OpenCode providers and Antigravity: `--continue`.
- Ollama: no resume possible.
- The app remembers which engine an agent used. Changing provider or model starts a new chat (`ai/cli_sessions.py`).
- The screen history shown in the terminal is kept in `data/storage/terminals/<agent>.bin`.
- **Not verified live** for Codex, Gemini, Antigravity: the resume flags are checked by printing commands, not by a real restart.

## 5. Inbox and reports

What exists now (`core/inbox.py`, `core/__main__.py`):

- Main agent sends a task with `task_send` (to one agent id, with a subject and body). The message is saved in the receiver's `inbox/`.
- Every 3 seconds the app types each waiting message into the receiver's terminal, then moves it to `inbox/.done/`.
- An agent replies by writing one JSON file into its own `outbox/`. The app moves it into the receiver's inbox.
- Messages wait 8 seconds after a terminal starts before being typed (`INBOX_SETTLE_S`), so they are not lost on a half-drawn screen.

What is planned (agreed with Thalha, not yet built):

1. **Start-up inbox file.** On every app start, each agent gets one file, `data/storage/briefings/<agent>-inbox.md`, containing:
   - its waiting messages (sender, subject, body, time);
   - its open tasks from the board;
   - the agents it can message and how (write one JSON file into its outbox, with `to`, `subject`, `body`);
   - the rules: reply only when needed; never message the user directly.
   The agent is pointed at this file in the same way as its briefing.
2. **Report back to the main agent.** Each normal agent reports to Hippoherman through its outbox when a task is done, blocked, or needs a decision. The report has a fixed shape: task id, status (done / blocked / question), what changed, what is next. Hippoherman's inbox receives it like any message.
3. **Inbox on new agent.** When a new agent is added and its terminal opens, it gets the start-up inbox file at once.

Open decision: whether Hippoherman should reply to each report or only act on blocked and question reports. Proposed default: act on blocked and question reports, and log the rest.

## 6. Monitor and status

- Monitor tab: the Watchers section is removed. Directories are shown unwrapped. The dropdown caret is solid.
- The agent bar and the Monitor card show model, provider, command and context %. They refresh every 3 seconds.
- Stats (last command, tokens) for non-Claude providers are **not started**. Each CLI needs its own session reader.

## 7. Settings, keys and engine apply

- Keys are saved in the app's key store. A provider needing a key shows an error on apply when none is saved.
- A CLI provider shows an error on apply when its CLI is not on PATH. Ollama must be running.
- Apply restarts the main terminal with the new engine. Checks are in `engine_problem()` in `core/terminal.py`.

## 8. Known gaps and risks

- **Briefing for non-OpenCode CLIs is unconfirmed.** The pointer is typed after a fixed delay. A new log line (`briefing pointer sent / skipped / failed`) in the agent events file will show what happened.
- **Working tree has 76 uncommitted changes.** Many are UI and asset changes not made in this session. They must be reviewed before any commit.
- **Repo is not ready to publish.** One hardcoded personal path: `app/e2e/tauri-mock.ts:199`. A full scan for machine-specific paths has not been done.
- **DeepSeek CLI** install is pending Thalha's choice of package.
- **Provider model names** for 2026 are not checked against live APIs.
- **Stale ESLint/Svelte warnings**: 14 unused-CSS warnings already in the UI (not introduced here).

## 9. Next steps, in order

1. Confirm the briefing reaches each CLI type after a restart (test: one new agent per provider family).
2. Build the start-up inbox file (section 5, item 1) and the new-agent inbox delivery (item 3).
3. Build the report-back format and Hippoherman's handling (item 2).
4. Resume checks for Codex, Gemini and Antigravity with a real restart.
5. Stats readers for non-Claude providers.
6. Clean and review the working tree; commit in logical pieces.
7. Scan for machine-specific paths and fix `app/e2e/tauri-mock.ts:199` before publishing to GitHub.

## 10. How to verify

- `.venv/bin/python -m pytest tests/core` (211 passed at last run).
- `npm run check` in `app/` for the UI.
- Live: start an agent per provider family, read its terminal and its `data/storage/agent-events.jsonl` for the briefing and inbox lines.
