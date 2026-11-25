# Hippocampus: whole system plan

Status as of 2026-11-25. Written for Thalha and for any agent that starts work on Hippocampus.

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

**Built:** `core/startup_inbox.py` writes a per-agent start-up inbox with waiting messages, the current roster, message schema, open tasks and reply rules. `core/session_hive.py` refreshes it on app start and before a new agent session. The briefing points the agent to that inbox, and the delivery loop types it after the terminal settles. Agents report through the validated outbox schema; acknowledgement-only messages are dropped.

## 6. Monitor and status

- Monitor tab: the Watchers section is removed. Directories are shown unwrapped. The dropdown caret is solid.
- The agent bar and the Monitor card show model, provider, command and context %. They refresh every 3 seconds.
- The agent bar shows the running command and context. Token totals are available from Claude folder logs and provider-specific local logs where supported; they are not a uniform per-session measure across every CLI.
- 7.30 offers English, Simplified Chinese and Arabic. Arabic layout uses logical CSS properties, but most screen copy still needs translation wrapping and catalogue entries.
- Ask-first behavior is provider-specific: Claude Code's hook sends command and file-change requests to the app's Ask me page. Codex uses its `on-request` approval policy, and Gemini CLI uses its `default` approval mode; those prompts stay in the agent's terminal and do not enter Ask me. The agent card and Ask me page state this limitation.

## 7. Settings, keys and engine apply

- Keys are saved in the app's key store. A provider needing a key shows an error on apply when none is saved.
- A CLI provider shows an error on apply when its CLI is not on PATH. Ollama must be running.
- Apply restarts the main terminal with the new engine. Checks are in `engine_problem()` in `core/terminal.py`.

## 8. Known gaps and risks

- **Briefing for non-OpenCode CLIs is unconfirmed.** The pointer is typed after a fixed delay. A new log line (`briefing pointer sent / skipped / failed`) in the agent events file will show what happened.
- **Provider session resume and briefing delivery** still need a live restart check for Codex, Gemini CLI and Antigravity; unit tests verify the command flags, not a live session.
- **Provider model names** should be checked against the installed CLIs when adding or changing model choices.

## 9. Next steps, in order

1. Confirm the briefing and start-up inbox reach each CLI type after a restart (test one new agent per provider family).
2. Verify Codex, Gemini CLI and Antigravity resume behavior with a real restart.
3. Continue checking provider model names when the CLIs update.

## 10. How to verify

- `.venv/bin/python -m pytest -q tests` and the Python linter.
- `npx svelte-check`, ESLint, TypeScript and `npm test` in `app/`.
- Live: start an agent per provider family, read its terminal and its `data/storage/agent-events.jsonl` for the briefing and inbox lines.
