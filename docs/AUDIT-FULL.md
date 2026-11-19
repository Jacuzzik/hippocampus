# Hippocampus full app audit

Audited by: hippo-full-audit (temp). Date: 2026-11-01.

## Scope and method

- **Source audited:** commit `96121a1` (branch `agent/worker-hippo-full-audit`, same HEAD as this worktree). Read-only; no source file, no `config/settings.toml` changed.
- **Not audited:** uncommitted edits in `worktrees/hippo-card-faces-kelly-match` (9 modified UI files: `App.svelte`, `assistant/Assistant.svelte`, `assistant/session.svelte.ts`, `owner/AgentBar.svelte`, `owner/AgentPanel.svelte`, `owner/addedAgents.svelte.ts`, `regions/GraphRegion.svelte`, `regions/MonitorPanel.svelte`, `regions/RightPanel.svelte`; plus 2 new files). The earlier final report's "batch 3" removals (dummy buttons, voice, IDE/Git tabs) exist only there, not in `96121a1`. Verdicts for those files may differ in that working tree.
- **Controls:** every `onclick`, `onchange`, `onsubmit`, `onkeydown`, `oninput`, `onpointerdown`, `bind:value` and `bind:checked` in `app/ui/**/*.svelte` (141 lines) was read in place and given a verdict. Unmounted files are listed separately and not counted.
- **Sidecar names:** all 52 method names the UI sends were diffed against the `dispatch` table in `core/__main__.py` (59 names). **0 UI calls are missing from the sidecar.**
- **Smoke test:** read-only sidecar methods run on a temp storage and temp settings copy, using `hippocampus-full-build-2026-10-26/.venv/bin/python`. Response shapes match what the UI reads for `account`, `budget`, `network`, `watchers`, `system`, `skills`, `keys`, `provider_status`, `memory_status`, `memory`, `settings`, `tasks`, `inbox`, `jobs`, `helpers`, `webhooks`, `agents`, `asks`, `activity`, `cards`, `tools`, `chat_history`, `agent_session`. `share` with a valid password returns "No share host is set up". `memory_search` in meaning mode returns "not set up".
- **Not run:** `npx svelte-check`. It fails on this worktree because `app/node_modules` lacks `@tsconfig/svelte` and `@sveltejs/vite-plugin-svelte`. No compile result is claimed.

Verdict key: **WIRED** = real data or action end to end. **FAKE** = shows or does something not real. **NOT SET UP** = needs a service, key, or host this build lacks. **BUG** = wrong behaviour in code that is wired.

---

## WIRED

| Item | Location | Evidence |
|---|---|---|
| Window Escape closes menus and info box | `owner/AgentBar.svelte:90` | local state reset |
| Card menu "Open" (shows info box) | `owner/AgentBar.svelte:109` | `showInfo()`, label says Open but opens the info box only |
| Card menu "Add note" / "Rename" | `owner/AgentBar.svelte:118`, `:126` | `startEdit()` in `owner/addedAgents.svelte.ts` |
| Card menu "Archive" | `owner/AgentBar.svelte:134` | `archiveAgent()` → localStorage |
| Card menu "Delete" | `owner/AgentBar.svelte:144` | `removeAgent()` → `save_agents` (list only; terminal and folder untouched) |
| Rename / note inputs | `owner/AgentBar.svelte:166`, `:168` | `bind:value` on `agentEdit` |
| Edit Cancel / Save | `owner/AgentBar.svelte:171`, `:172` | `saveEdit()` → `save_agents` |
| Info box close | `owner/AgentBar.svelte:194` | local state |
| Card right-click menu | `owner/AgentBar.svelte` (`oncontextmenu`) | `openMenu()` |
| Card select | `owner/AgentBar.svelte:281` | `selectAgent()` |
| HIPPO INFO | `owner/AgentBar.svelte:257` | local info; MODEL from `account` |
| "+ Add agent" | `owner/AgentBar.svelte:322` | `onadd` → dialog |
| AgentPanel resize sync | `owner/AgentPanel.svelte:30` | `sidecar_call terminal_resize` → `core/__main__.py` `terminal()` |
| Terminal keystrokes | `owner/AgentPanel.svelte:48` | `terminal_input` → `core/terminal.py` `write()` |
| Terminal start (claude, codex) | `owner/AgentPanel.svelte:66` | `terminal_start` → `core/terminal.py:35` `_command()` |
| Card "Edit" (rename) | `owner/AgentPanel.svelte:113` | `startEdit()` |
| AgentPanel close × | `owner/AgentPanel.svelte:120` | `selection.id = null` |
| Composer submit | `owner/AgentPanel.svelte:159`, `:160`, `:161` | `send()` → `terminal_input` |
| AgentPanel "Add note" / "Delete" | `owner/AgentPanel.svelte:174`, `:175` | `startEdit()` / `removeAgent()` |
| Assistant Escape to stop | `assistant/Assistant.svelte:79` | `assistant.stop()` → `stop` → `kill.trigger()` |
| Session select | `assistant/Assistant.svelte:91` | `showSession()` (past sessions read-only) |
| New session | `assistant/Assistant.svelte:98` | `new_session` → `cli_sessions.switch()` |
| Approve / Decline | `assistant/Assistant.svelte:129`, `:133` | `confirm` → `core/__main__.py:306` `confirm()` → gate |
| Ask form submit / textarea | `assistant/Assistant.svelte:144`, `:148` | `answer` → `core/__main__.py:337` |
| Allow one more request | `assistant/Assistant.svelte:188` | `budget_allow` → `allowance = True` |
| Continue | `assistant/Assistant.svelte:197` | `chat` with `continue: true` |
| Composer submit / draft | `assistant/Assistant.svelte:202`, `:225` | `send()` → `chat` (`core/__main__.py:257`) |
| Remove attached file | `assistant/Assistant.svelte:215` | local array |
| "+ files" | `assistant/Assistant.svelte:245`, `:239` | file input, 100 KB cap, text sent inline |
| Stop | `assistant/Assistant.svelte:260` | `stop` |
| Add agent: name, avatar, folder, isolation, provider, model, autonomy, template, description, goal, back/next/spawn | `control/AddAgentDialog.svelte:140`, `:149`, `:190`, `:208`, `:214`, `:237`, `:243`, `:246`, `:252`–`:259` | Spawn → `addAgent()` → `agent_session` (see BUG and FAKE rows for what is not used) |
| Activity filter buttons, Refresh | `control/ActivitySection.svelte:46`, `:49` | `activity` (`limit: 200`) |
| Asks: answer input, Enter, Respond | `control/AsksSection.svelte:62`, `:63`, `:65` | `answer` |
| Budget caps inputs, Save caps | `control/BudgetSection.svelte:127`, `:135` | `set_budget` → `core/__main__.py:418` |
| Budget Allow one more request | `control/BudgetSection.svelte:139` | `budget_allow` |
| Skill remove (two clicks) | `control/CapabilitiesSection.svelte:107` | `remove_skill` (`approve: true`) |
| Skill install path, Install (two clicks) | `control/CapabilitiesSection.svelte:119`, `:120`, `:122` | `install_skill` |
| Control dialog settings button, close | `control/ControlDialog.svelte:46`, `:53` | local state |
| Dispatch: agent select, task, Review, Send, Cancel | `control/DispatchSection.svelte:47`, `:57`, `:64`, `:65`, `:70` | Send → `start_helper` (only "Helper" is enabled) |
| Helpers: prompt, Start helper | `control/HelpersSection.svelte:63`, `:69` | `start_helper` (limit 4, budget gate) |
| Jobs: enable toggle, every-days | `control/JobsSection.svelte:62`, `:75` | `set_job` → `core/jobs.py`; scheduler thread runs due jobs (`core/__main__.py:_schedule`) |
| Keys: draft input, Save, Clear | `control/KeysSection.svelte:78`, `:80`, `:83` | `save_key` / `clear_key` → OS keychain |
| Memory: By text / By meaning, search, query | `control/MemorySection.svelte:60`, `:67`, `:78`, `:87` | `memory_search`; text mode works (meaning mode is NOT SET UP, see below) |
| Network mode choose | `control/NetworkSection.svelte:50` | `set_network`; enforced in `ai/providers/base.py:69` and `ai/providers/claude_cli.py:40` |
| Settings dialog close, tabs | `control/SettingsDialog.svelte:50`, `:62` | local tabs; Python sidecar status via `network` |
| Account: vault form, Choose folder | `overlays/AccountDialog.svelte:141`, `:147`, `:153` | `set_vault` → `core/__main__.py:441` |
| Account: sign-in form and key | `overlays/AccountDialog.svelte:171`, `:173` | `sign_in` → keychain |
| Account: Sign out (two presses) | `overlays/AccountDialog.svelte:164` | `sign_out` |
| Account: Remove data (two presses) | `overlays/AccountDialog.svelte:192` | `remove_data` (index cache and key; notes untouched) |
| Account dialog Escape | `overlays/AccountDialog.svelte:136` | local |
| Command palette: query, keys, choose | `overlays/CommandBox.svelte:83`, `:84`, `:106` | runs the chosen command |
| Tools dialog: Every tool, per-tool toggles, Escape | `overlays/ToolsDialog.svelte:74`, `:87`, `:103` | `set_tools` (`names` or `null`) |
| Archived list: restore | `control/ArchivedAgentsSection.svelte:25` | `setArchived()` → localStorage |
| Shared folder open, copy path, remove skill | `control/SkillsSection.svelte:77`, `:80`, `:83` | `open_skill_folder`, clipboard, `remove_skill` |
| App shortcuts (F11, Ctrl+O/P/F), column resize | `App.svelte:176`, `:268`, `:277` | local state; resize sets CSS variables |
| Ribbon: note list, assistant, control panel, account | `regions/Ribbon.svelte:22`, `:34`, `:45`, `:58` | local state and dialogs |
| Right panel tabs (12, all live) and HIPPO tab | `regions/RightPanel.svelte:59`, `:69` | local state |
| Right panel text size − / + | `regions/RightPanel.svelte:77`, `:79` | `--term-size` read at `assistant/Assistant.svelte:374` |
| Note sidebar search, Enter opens first match | `regions/NoteSidebar.svelte:42`, `:43` | `matchFilter()` (`graph/model.ts`); App focuses via `bind:searchEl` |
| Memory only, tag select, tag chips, note list | `regions/NoteSidebar.svelte:51`, `:55`, `:73`, `:90` | filters shared with graph |
| Graph full-screen layout | `regions/GraphRegion.svelte:63` | `fullscreen` prop |
| Graph: Fit, Hide orphans, Hide names | `graph/BrainGraph.svelte:600`, `:602`, `:605` | `fitAll()`; checkboxes `bind:checked` |
| Graph: key colour pick, reset | `graph/BrainGraph.svelte:619`, `:622` | `setPick()` → localStorage |
| Graph: window keys (Esc, arrows) | `graph/BrainGraph.svelte:576` | `onselect(null)`, pan |
| Graph drawer: close, links to/from, wiki links | `graph/BrainGraph.svelte:643`, `:685`, `:698`, `:720` | `open(id)` → `onselect` |
| Graph drawer note body | `graph/BrainGraph.svelte:294` | `read` → `core/__main__.py:248` |
| Status bar counts | `regions/StatusBar.svelte` | `graph` data |
| Monitor: network, system (5 s), budgets, watchers | `regions/MonitorPanel.svelte` | `network`, `system`, `budget`, `watchers` |
| Graph panel: counts and most-linked | `regions/GraphPanel.svelte` | `graph` (read once) |
| Memory, Inbox, Tasks, Skills panels | `regions/MemoryPanel.svelte`, `InboxPanel.svelte`, `TasksPanel.svelte`, `SkillsPanel.svelte` | `memory`, `inbox`, `tasks`, `skills` (read once) |
| History panel (past events only) | `regions/HistoryPanel.svelte` | `activity` filtered |
| Temps panel | `regions/TempsPanel.svelte` | `helpers` (read once) |
| Triggers section (network, jobs, webhooks) | `control/TriggersSection.svelte` | read only: `network`, `jobs`, `webhooks` |
| Asks/Helpers polling | `control/AsksSection.svelte:41`, `control/HelpersSection.svelte:53` | 3 s / 2 s timers |
| Sidecar: 52 UI method names all have a dispatch branch | `core/__main__.py:757` `dispatch()` and `simple` / `extra` tables (`:823`–`:867`) | diff run; 0 missing |

## FAKE

| Item | Location | Evidence |
|---|---|---|
| Added-agent card "CTX" bar: 8 empty segments, "—" percentage (all cards) | `owner/AgentBar.svelte:244`, `:246`, `:302`, `:304` | `CTX_SEGMENTS` never filled; no context value reaches the UI |
| Info box BOSS, STATUS, CTX for added agents | `owner/AgentBar.svelte` `showInfo()` | `boss: NO_DATA`, `status: NO_DATA`, `ctx: NO_DATA` |
| Info box BOSS, CTX for HIPPO | `owner/AgentBar.svelte:257` | `boss: NO_DATA`, `ctx: NO_DATA` |
| Assistant "live · pty hippo" label | `regions/RightPanel.svelte:75` | the assistant is a chat request (`chat`), not a PTY; label says "live pty" |
| AgentPanel "live · pty <id>" label | `owner/AgentPanel.svelte:145` | static text, not state |
| AgentPanel IDE / auto / Open buttons (no handler) | `owner/AgentPanel.svelte:115`, `:116`, `:118`, `:119` | no `onclick` |
| AgentPanel Block tools, Stop after this step, ▶ 1:1 (no handler) | `owner/AgentPanel.svelte:127`–`:129` | no `onclick` |
| AgentPanel note input and "steer" button (no handler) | `owner/AgentPanel.svelte:133`, `:134` | no `bind:value`, no `onclick` |
| AgentPanel Git / Messages / Traces tabs (no handler) | `owner/AgentPanel.svelte:139`–`:141` | `aria-pressed` only |
| AgentPanel text size − / 12px / + (no handler) | `owner/AgentPanel.svelte:146` | static "12px" |
| AgentPanel voice / + files / + folder (no handler) | `owner/AgentPanel.svelte:167`–`:169` | "Dummy attachment buttons" comment in code |
| Graph Theme button (no handler) | `regions/GraphRegion.svelte:70` | title "Theme (not wired yet)" |
| Graph Personal board button (no handler) | `regions/GraphRegion.svelte:76` | title "Personal board (not wired yet)" |
| Add agent: Colour swatch (saved, never shown) | `control/AddAgentDialog.svelte:182` | `draft.colour` is only read in `control/model.ts:293`; no component uses it |
| Add agent: Isolation select (saved, no effect) | `control/AddAgentDialog.svelte:196` | value not read by any backend or terminal code |
| Add agent: Resume checkbox (saved, no effect) | `control/AddAgentDialog.svelte:203` | `draft.resume` never sent; sessions always resume by id |
| Add agent: Goal textarea (required, then unused) | `control/AddAgentDialog.svelte:246` | validated at `control/model.ts:316`, never displayed or sent |
| Add agent: Autonomy select (no effect on the running CLI) | `control/AddAgentDialog.svelte:222` | only changes the preview string (`control/model.ts:362`); see BUG |

## NOT SET UP

| Item | Location | Evidence |
|---|---|---|
| Assistant "voice" button | `assistant/Assistant.svelte:250` | shows "No speech-to-text source is set up" (honest); no `voice/` module |
| Card TALK buttons (HIPPO and added agents) | `owner/AgentBar.svelte:250`, `:309` | `disabled`, title "Talk is not set up yet" |
| Card CMD row ("—", all cards) | `owner/AgentBar.svelte:238`–`:239`, `:296`–`:297` | no data source |
| Added-card ONLINE dot ("—") | `owner/AgentBar.svelte:290` | no per-agent status |
| AgentPanel stats: Cost, Tokens, Agent time, Context ("—") | `owner/AgentPanel.svelte:152`–`:155` | honest dash; no per-agent usage in this commit |
| AgentPanel status "Not reported" | `owner/AgentPanel.svelte:14`, `:109` | honest text |
| Terminal for providers other than Claude and Codex (gemini-cli, ollama, API providers) | `core/terminal.py:20`, `:101`–`:102` | "The terminal does not run … yet. Claude and Codex work." shown in the panel |
| Dispatch "Assistant (Not set up)" option | `control/DispatchSection.svelte:6`–`:9`, `:47`–`:53` | `disabled` option |
| Share: password, minutes, Make link | `control/ShareSection.svelte:36`, `:45`, `:49` | `core/__main__.py:665` `share_note()` always raises "No share host is set up" (honest) |
| Teams: Start a team | `control/TeamsSection.svelte:16` | message "Not set up: teams need the team service…" (honest) |
| Capabilities: MCP servers and plugins lists | `control/CapabilitiesSection.svelte:9`–`:10` | hard-coded empty arrays, labelled "Not set up" |
| Memory: search by meaning | `control/MemorySection.svelte:67` | backend `core/memory.py:97` raises `NotSetUp` (no embedder) |
| Chat without a Claude key and without Ollama | `core/__main__.py:257` (`chat`) | `build_router()` fails; key or Ollama needed |
| Settings: "Local model (Ollama)" row | `control/SettingsDialog.svelte:59`–`:60` | honest text "this build does not check for it" |

## BUG

| Item | Location | Evidence |
|---|---|---|
| Added-agent card status shows the HIPPO assistant's orb state for every agent | `owner/AgentBar.svelte:318` (and `:270` for HIPPO) | `<span class="status">{ORB_LABELS[assistant.chat.orb]}</span>` in the added-agent block; each agent shows the assistant's state |
| Switching tabs away from an agent kills its CLI | `owner/AgentPanel.svelte:79`–`:84` with `regions/RightPanel.svelte` `{#if tab === "agent" && agent}` | `onDestroy` sends `terminal_stop`; `core/terminal.py:70`–`:74` `stop()` calls `terminate()`. Any tab switch unmounts the panel, so a running agent is stopped. The assistant is kept mounted for this reason; agents are not |
| Agent folder is never created and never used | `control/AddAgentDialog.svelte:190`, `:309`–`:310`; `core/terminal.py:39` | the app does not `mkdir` the folder (only validated non-empty). `subprocess.Popen` has no `cwd=`, so the CLI runs in the app's directory |
| Model field is not passed to the CLI | `control/AddAgentDialog.svelte:214`; `core/terminal.py:99`–`:110` | `_command()` builds only `[binary, --session-id|--resume, id]` (or `[binary]` for codex); `--model` is never added, though the card shows the model |
| Autonomy preview promises a flag the terminal does not pass | `control/AddAgentDialog.svelte:52`, `:222`; `control/model.ts:362`; `core/terminal.py:108`–`:110` | preview shows `--permission-mode bypassPermissions`; the terminal runs `claude --session-id …` with no permission flag. The autonomy choice has no effect |
| Provider "OpenAI" (API key kind) runs the Codex CLI | `core/terminal.py:20` | `CLI_FOR` maps `"openai"` to `codex`; uses the Codex login, not the saved key |
| ActivityPanel says "live" but loads once | `regions/ActivityPanel.svelte:1` (comment), `:19` (`onMount` only) | no timer (only Monitor, GraphRegion, Asks, Helpers poll). Same for TempsPanel, HistoryPanel, TasksPanel, InboxPanel, MemoryPanel, SkillsPanel, GraphPanel: stale until remount |
| Duplicate `card_list`, `card_create`, `card_update` definitions | `core/__main__.py:346`–`:358` and `:360`–`:372` | second copy silently overrides the first (identical); remove one |
| `chat` consumes the allowance and pause before validating `continue` | `core/__main__.py:266`–`:269` | `allowance` set to False and `paused` cleared before the "nothing is paused" check raises |
| Dead components (not on screen): OwnerPanel, AgentStatus, SettingsFloat, SettingsPanel | `owner/OwnerPanel.svelte`, `owner/AgentStatus.svelte`, `regions/SettingsFloat.svelte`, `regions/SettingsPanel.svelte` | no import from any mounted file. SettingsPanel also maps "Max turns per run" to `max_tool_calls` but labels it "tool calls per request" (line `valueOf`). Not counted below |

## BACKEND WITHOUT UI

| Method | Location | Evidence |
|---|---|---|
| `open` | `core/__main__.py:136` (dispatch `:761`) | no `sidecar_call` with `open`; the app uses `set_vault` |
| `cards` / `card_create` / `card_update` | `core/__main__.py:346`–`:372` | not called from `app/ui`; the Command Center cards feature is not in this UI |
| `save_webhook` / `delete_webhook` / `run_webhook` | `core/__main__.py:676`–`:700` | no UI to create or run webhooks; TriggersSection only lists them |

Notes: `run_webhook` would raise `KeyError` on an unknown `kind` (`core/__main__.py:695`); it is not reachable from the UI.

---

## Counts

| Section | Count |
|---|---|
| WIRED | 75 |
| FAKE | 18 |
| NOT SET UP | 14 |
| BUG | 10 |

BACKEND WITHOUT UI: 7 methods in 3 rows (listed above). Unmounted files are not counted. Counts are table rows; a row may group several identical controls.
