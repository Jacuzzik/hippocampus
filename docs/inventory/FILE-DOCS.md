# File guide: Hippocampus app

Generated from each file's header comment and its top-level names. A line is the file's stated purpose; the names are what it defines or exports. Read the file for the detail.

Missing from disk (tracked in git, deleted in working tree): app/ui/owner/AgentStatus.svelte, app/ui/owner/OwnerPanel.svelte, app/ui/regions/SettingsFloat.svelte, app/ui/regions/SettingsPanel.svelte.

## `ai/__init__.py`
- Purpose: The assistant: model providers, the router that picks one, and the tool loop.
- Defines: (none at top level)

## `ai/agent.py`
- Purpose: The assistant loop: ask the model, run the tools it asks for, repeat until it answers.
- Defines: AgentError, AgentPaused, Agent

## `ai/chat_history.py`
- Purpose: The chat window's sessions per agent, on disk, so they show again after a restart.
- Defines: _clean, _read, load, save, model_turns

## `ai/cli_sessions.py`
- Purpose: One Claude Code session per agent, kept on disk so it survives an app restart.
- Defines: _read, get, mark_started, has_transcript, switch, folder_tokens, folder_activity, codex_tokens, context_percent, _transcript, open_tool_calls, last_tool_call, last_model, _write

## `ai/keys.py`
- Purpose: API keys for model providers, kept in the OS keychain. Never written to a file or a log.
- Defines: _account, get_key, key_hint, set_key, clear_key, get_api_key, set_api_key, clear_api_key

## `ai/network.py`
- Purpose: The network switch: which directions the app may reach outside this machine.
- Defines: set_mode, mode, allows_model_calls

## `ai/providers/__init__.py`
- Purpose: Model providers. Each one implements `Provider` from base.py.
- Defines: (none at top level)

## `ai/providers/base.py`
- Purpose: The provider interface and the shared HTTP helper.
- Defines: ProviderError, ToolCall, ToolSpec, Reply, NetworkBlocked, Provider, post_json, _post

## `ai/providers/claude.py`
- Purpose: Claude over the Anthropic Messages API, with the user's own API key.
- Defines: ClaudeProvider, to_claude, parse_claude

## `ai/providers/claude_cli.py`
- Purpose: Claude through the Claude Code CLI, logged in with the user's own account. No API key is used.
- Defines: cli_ready, _newest, ClaudeCliProvider

## `ai/providers/ollama.py`
- Purpose: Ollama on this machine: the free, offline fallback.
- Defines: OllamaProvider, to_ollama, parse_ollama

## `ai/providers/openai_compat.py`
- Purpose: OpenAI-style chat endpoints. One provider class serves every service that speaks this API.
- Defines: Preset, OpenAICompatProvider, to_openai, parse_openai

## `ai/router.py`
- Purpose: Picks the model per reply: Claude when a key is set; Ollama otherwise, or when Claude fails.
- Defines: Router, model_name, build_router, _primary

## `app/e2e/account.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/control.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/critical-paths.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/graph-drag.spec.ts`
- Purpose: Labels sit 8px right of and 7px above the node's screen point (see BrainGraph.svelte drawLabels).
- Defines: (none at top level)

## `app/e2e/graph-fallback.spec.ts`
- Purpose: Simulates a browser with no WebGL 2 (some phone browsers): the graph must still draw.
- Defines: (none at top level)

## `app/e2e/note-drawer.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/notes-features.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/orphans.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/owner-panel.spec.ts`
- Purpose: The provider is shown in the HIPPO details (INFO), not on the bar.
- Defines: (none at top level)

## `app/e2e/responsive.spec.ts`
- Purpose: Phone and tablet sizes. Phones span 360 to 430px wide; tablets are portrait and landscape.
- Defines: (none at top level)

## `app/e2e/right-panel-tabs.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/settings.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/tauri-mock.ts`
- Purpose: Only the part of Playwright's Page this file uses, so the app can import it without Playwright.
- Defines: mockSidecar

## `app/e2e/tools.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/e2e/zz-assistant-shots.spec.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/eslint.config.js`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/playwright.config.ts`
- Purpose: The UI runs in a plain browser with the Tauri bridge mocked (e2e/tauri-mock.ts), so no
- Defines: (none at top level)

## `app/playwright.tmp-rp.config.ts`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/scripts/agent-card.test.mjs`
- Purpose: Tests for ui/assistant/agentCard.ts: faces exist, the face pick is stable, and each accent's text passes AA.
- Defines: (none at top level)

## `app/scripts/allowlist.test.mjs`
- Purpose: Tests for ui/overlays/allowlist.ts. Node 24 strips the types when it imports the .ts file.
- Defines: (none at top level)

## `app/scripts/assistant-model.test.mjs`
- Purpose: Tests for ui/assistant/model.ts. Node 24 strips the types when it imports the .ts file.
- Defines: (none at top level)

## `app/scripts/build-tokens.mjs`
- Purpose: Generates ui/styles/tokens.css from design/tokens.json, the single source of
- Defines: TOKENS_PATH, CSS_PATH, loadTokens, resolveValue, fontStack, buildVariables, buildCss

## `app/scripts/check-tokens.mjs`
- Purpose: Run with `node --test scripts/check-tokens.mjs`. Enforces the design-token
- Defines: (none at top level)

## `app/scripts/contrast.test.mjs`
- Purpose: WCAG 2.1 AA contrast for the text colours the UI uses, computed from design/tokens.json.
- Defines: (none at top level)

## `app/scripts/control.test.mjs`
- Purpose: Tests for ui/control/model.ts. Node 24 strips the types when it imports the .ts file.
- Defines: (none at top level)

## `app/scripts/graph-model.test.mjs`
- Purpose: Tests for ui/graph/model.ts. Node 24 strips the types when it imports the .ts file.
- Defines: (none at top level)

## `app/scripts/markdown.test.mjs`
- Purpose: Tests for ui/graph/markdown.ts. Node 24 strips the types when it imports the .ts file.
- Defines: (none at top level)

## `app/src-tauri/build.rs`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/src-tauri/src/lib.rs`
- Purpose: no header comment; read the file
- Defines: run

## `app/src-tauri/src/main.rs`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/src-tauri/src/sidecar.rs`
- Purpose: The Python sidecar: `python -m core serve`. One JSON request per line on its stdin, one
- Defines: sidecar_call

## `app/svelte.config.js`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `app/ui/App.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/assistant/AgentCard.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/assistant/Assistant.svelte`
- Purpose: When given, the message goes here (the Control Room sends it to the terminal) instead of the chat.
- Defines: (component)

## `app/ui/assistant/Orb.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/assistant/agentCard.ts`
- Purpose: The agent card's pure model: accent colours, avatars and the avatar pick. No DOM, so it runs under node --test.
- Defines: ACCENTS, Accent, FACES, faceFor

## `app/ui/assistant/model.ts`
- Purpose: Pure chat state: messages, tool log, confirm cards and the orb state. No DOM or Tauri, so it runs under node --test.
- Defines: OrbState, ToolStatus, Message, ToolEntry, ConfirmCard, AskCard, ActivityEntry, Chat, BudgetPause, SidecarEvent, TOOL_LOG_LIMIT, emptyChat, clockTime, logActivity, sendMessage

## `app/ui/assistant/session.svelte.ts`
- Purpose: The assistant's live state, shared by the chat panel and the orb. Talks to the sidecar through the Tauri bridge.
- Defines: SavedSession, assistant

## `app/ui/control/ActivitySection.svelte`
- Purpose: One list of handoffs, tool calls, approvals, errors and settings changes, newest first.
- Defines: (component)

## `app/ui/control/AddAgentDialog.svelte`
- Purpose: The Add agent dialog: four steps, then Spawn adds the agent to the agent bar.
- Defines: (component)

## `app/ui/control/ArchivedAgentsSection.svelte`
- Purpose: Agents archived from their card menu in the bottom bar; restoring one shows it there again.
- Defines: (component)

## `app/ui/control/AsksSection.svelte`
- Purpose: Questions the assistant cannot answer alone, from every chat, in one place.
- Defines: (component)

## `app/ui/control/BudgetSection.svelte`
- Purpose: Token caps per day, week and month. 0 means no cap. Over a cap, the assistant pauses.
- Defines: (component)

## `app/ui/control/CapabilitiesSection.svelte`
- Purpose: What the app can use: MCP servers, skills and plugins. Skills can be installed from a folder
- Defines: (component)

## `app/ui/control/ControlDialog.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/control/DispatchSection.svelte`
- Purpose: Sends a task to an agent. Nothing is sent until you confirm the exact task shown.
- Defines: (component)

## `app/ui/control/HelpersSection.svelte`
- Purpose: Short-lived helpers: one prompt, run once, result reported back. Four run at once, at most.
- Defines: (component)

## `app/ui/control/JobsSection.svelte`
- Purpose: Repeating jobs over the notes. Each runs when it is due, about once a minute is checked.
- Defines: (component)

## `app/ui/control/KeysSection.svelte`
- Purpose: Saved keys are kept in the OS keychain. A saved key takes effect on the next request.
- Defines: (component)

## `app/ui/control/MemorySection.svelte`
- Purpose: Search the assistant's memory notes. Text search always works. Search by meaning
- Defines: (component)

## `app/ui/control/NetworkSection.svelte`
- Purpose: Which directions the app may reach outside this machine. Off is the default.
- Defines: (component)

## `app/ui/control/SettingsDialog.svelte`
- Purpose: Settings in six tabs. The panels reuse the control panel sections, so each setting has one home.
- Defines: (component)

## `app/ui/control/ShareSection.svelte`
- Purpose: Password links for one note, 60 minutes by default. Links need a share host, which is not
- Defines: (component)

## `app/ui/control/SkillsSection.svelte`
- Purpose: Installed skills: folders under skills/ that hold a SKILL.md file.
- Defines: (component)

## `app/ui/control/TeamsSection.svelte`
- Purpose: Teams are shared agents across people. Nobody is enrolled in this build.
- Defines: (component)

## `app/ui/control/TriggersSection.svelte`
- Purpose: What starts work without you: the network state, scheduled jobs, context compaction and webhooks.
- Defines: (component)

## `app/ui/control/model.ts`
- Purpose: Pure helpers for the control panel. No DOM or Tauri, so they run under node --test.
- Defines: NETWORK_MODES, NetworkMode, NETWORK_TEXT, WINDOWS, Window, WINDOW_LABELS, Caps, Overrun, overrunOf, usageLine, parseCap, ActivityKind, ActivityRow, ACTIVITY_FILTERS, filterActivity

## `app/ui/fuzzy.ts`
- Purpose: Subsequence match: every character of `query` must appear in `text`, in order.
- Defines: fuzzyScore

## `app/ui/graph/BrainGraph.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/graph/colors.ts`
- Purpose: Reads design tokens (CSS custom properties from tokens.css) as RGBA 0 to 1, so no colour is hardcoded here.
- Defines: token, parse, hexOf

## `app/ui/graph/markdown.ts`
- Purpose: A small Markdown reader for the note drawer. It builds plain data, never HTML, so the
- Defines: Inline, Block, parseInline, parseNote

## `app/ui/graph/model.ts`
- Purpose: Pure graph logic: layout, camera, hit testing, filtering. No DOM or WebGL, so it runs under node --test.
- Defines: GraphNode, GraphData, LayoutPreset, LOW_POWER, Camera, MIN_ZOOM, MAX_ZOOM, mulberry32, LINK_DISTANCE, CENTER_STRENGTH, LONELY_PULL, REPEL_STRENGTH, REPEL_RANGE, REPEL_SOFTEN, REHEAT

## `app/ui/graph/renderer-canvas.ts`
- Purpose: 2D canvas renderer for the brain graph, used when WebGL 2 is missing (some phone browsers).
- Defines: Canvas2DRenderer

## `app/ui/graph/renderer.ts`
- Purpose: WebGL 2 renderer for the brain graph: edges as lines, nodes as instanced quads.
- Defines: Rgba, BrainRenderer

## `app/ui/main.ts`
- Purpose: Browser preview only (npm run dev in a normal browser): fake the desktop bridge with the test mock.
- Defines: (none at top level)

## `app/ui/overlays/AccountDialog.svelte`
- Purpose: Setup: the brain is the default vault the app creates on first start. Removing data keeps the notes.
- Defines: (component)

## `app/ui/overlays/CommandBox.svelte`
- Purpose: One item to pick: a note for the quick switcher, an action for the command palette.
- Defines: (component)

## `app/ui/overlays/ToolsDialog.svelte`
- Purpose: Which tools the assistant may use. Each change is saved at once; the settings file keeps it.
- Defines: (component)

## `app/ui/overlays/allowlist.ts`
- Purpose: Pure helpers for the assistant tools dialog. No DOM or Tauri, so they run under node --test.
- Defines: ToolRow, allowlistAfter

## `app/ui/owner/AgentBar.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/owner/AgentPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/owner/addedAgents.svelte.ts`
- Purpose: Agents the user created in the add-agent form. The sidecar keeps them in storage/agents.json;
- Defines: SavedAgent, addedAgents, archived, setArchived, addAgent, setAddedAgents, selection, selectAgent, agentEdit, startEdit, saveEdit, archiveAgent, removeAgent

## `app/ui/regions/ActivityPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/regions/GraphPanel.svelte`
- Purpose: Reloads every few seconds so notes the agents add or change show up without a restart.
- Defines: (component)

## `app/ui/regions/GraphRegion.svelte`
- Purpose: Read only, so a failed read just leaves the last value on screen.
- Defines: (component)

## `app/ui/regions/HistoryPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/regions/InboxPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/regions/MemoryPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/regions/MonitorPanel.svelte`
- Purpose: Only the agents the user added (addedAgents
- Defines: (component)

## `app/ui/regions/NoteSidebar.svelte`
- Purpose: Search, tag and memory filters and note list. The graph reads the same state through props.
- Defines: (component)

## `app/ui/regions/Ribbon.svelte`
- Purpose: Icon strip on the far left, as in the notes app's ribbon. Each button shows or hides one pane.
- Defines: (component)

## `app/ui/regions/RightPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/regions/SkillsPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/regions/StatusBar.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/regions/TasksPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/regions/TempsPanel.svelte`
- Purpose: no header comment; read the file
- Defines: (component)

## `app/ui/vite-env.d.ts`
- Purpose: <reference types="svelte" />
- Defines: (none at top level)

## `app/vite.config.ts`
- Purpose: Localhost only: the dev server must never listen on a public interface.
- Defines: (none at top level)

## `core/__init__.py`
- Purpose: Hippocampus core: notes engine. D1 ships only the sidecar stub.
- Defines: (none at top level)

## `core/__main__.py`
- Purpose: Sidecar entry point.
- Defines: Session, _watcher, _issues, _whole, handle, Writer, _method, _answer, _schedule, serve, index, _watch, watch, manage_key, _vault_dir

## `core/activity.py`
- Purpose: The activity log: handoffs, tool calls, approvals, errors and budget pauses, one JSON line each.
- Defines: record, read

## `core/added_agents.py`
- Purpose: Agents the user added in the app. Their list lives in storage/agents.json.
- Defines: load, save, _check

## `core/budget.py`
- Purpose: Token budgets: caps per day, week and month, for the whole app and for the assistant.
- Defines: Overrun, window_start, Ledger

## `core/cards.py`
- Purpose: Owner cards: small UI cards the main agent fills for the owner.
- Defines: CardStore, _text

## `core/helpers.py`
- Purpose: Short-lived helper jobs: each runs one prompt once and reports back. At most four run at once.
- Defines: HelperLimit, Helpers

## `core/jobs.py`
- Purpose: Scheduled notes jobs. Each job repeats every N days. Its state lives in storage/jobs.json.
- Defines: Job, load, save, set_job, is_due, run_due

## `core/memory.py`
- Purpose: Assistant memory notes: trimming long ones, and finding them by text or by meaning.
- Defines: NotSetUp, Embedder, is_memory, _is_section, trim_text, trim_memory_file, search_text, search_meaning, _cosine, status

## `core/settings.py`
- Purpose: Reads config/settings.toml. It holds no secrets: API keys live in the OS keychain.
- Defines: Caps, Settings, _tool_limit, _allowed_tools, _provider, _caps, load_settings, _replace_sections, _write, _read, save_allowed_tools, save_vault, save_network_mode, save_engine, save_budget

## `core/share.py`
- Purpose: Password links for one note. They expire 60 minutes after they are made, by default.
- Defines: expiry, request_link

## `core/skills.py`
- Purpose: Installed skills: folders under skills/ that hold a SKILL.md file.
- Defines: list_skills, _description, skill_folder, remove_skill, install_skill, open_folder

## `core/system_stats.py`
- Purpose: Host CPU, RAM and disk use, read only. Linux only: it reads /proc and calls statvfs.
- Defines: _cpu_times, cpu_percent, _meminfo, _ram_percent, _swap_percent, _disk_folder, _disk_percent, _disk_free_gb, SystemStats

## `core/terminal.py`
- Purpose: A real terminal per added agent: the agent's own CLI runs in a pseudo-terminal and its screen streams to the app.
- Defines: Terminals, _command

## `core/vault/__init__.py`
- Purpose: Vault indexing: scan Markdown notes, parse links and tags, keep a SQLite cache.
- Defines: open_index

## `core/vault/indexer.py`
- Purpose: Keep a vault's index in step with its files: a full sync, and change batches from the watcher.
- Defines: IndexStats, Indexer

## `core/vault/parser.py`
- Purpose: Parse one note's text into a title, wiki links and tags.
- Defines: Link, Tag, ParsedNote, normalize_target, parse_note, _blank, _split_frontmatter, _mask_code_and_comments, _title, _links, _make_tag, _inline_tags, _frontmatter_tags, _dedupe

## `core/vault/scanner.py`
- Purpose: Find the notes in a vault and read them safely.
- Defines: NoteFile, is_ignored, is_note_name, stat_note, iter_notes, read_note

## `core/vault/store.py`
- Purpose: SQLite index for one vault.
- Defines: index_path_for, check_sqlite_version, content_hash, NoteState, Store

## `core/vault/watcher.py`
- Purpose: Watch a vault and keep its index current while the app runs.
- Defines: StopEvent, VaultWatcher

## `core/webhooks.py`
- Purpose: Webhook triggers the user saves in the app. Their list lives in storage/webhooks.json.
- Defines: load, save, add, remove, find, _check

## `scripts/sidecar_entry.py`
- Purpose: PyInstaller entry point: the packaged sidecar runs `core` with the same arguments as `python -m core`.
- Defines: (none at top level)

## `tests/ai/test_openai_compat.py`
- Purpose: no header comment; read the file
- Defines: FakeHTTP, test_request_goes_to_the_preset_url_with_the_key_in_a_header_only, test_local_preset_sends_no_authorization_header, test_tool_call_round_trip, test_unexpected_reply_is_a_provider_error, test_catalog_offers_twenty_or_more_models

## `tests/ai/test_providers.py`
- Purpose: no header comment; read the file
- Defines: FakeHTTP, test_claude_sends_the_key_in_a_header_only, test_claude_round_trip_with_a_tool_call, test_claude_malformed_reply_is_a_provider_error, test_ollama_chat_and_tool_calls, test_ollama_history_conversion, test_http_error_names_the_host_not_the_key, test_unreachable_host_is_a_provider_error

## `tests/ai/test_router_and_keys.py`
- Purpose: no header comment; read the file
- Defines: Fake, ask, test_no_key_uses_ollama, test_key_uses_claude_and_falls_back_when_it_fails, test_both_failing_names_both, test_build_router_picks_claude_only_with_a_key, test_model_name_is_the_one_replies_come_from, MemoryKeyring, test_key_round_trip_through_the_keychain, test_keychain_failure_means_no_key, test_build_router_uses_the_chosen_preset_with_its_key, test_chosen_preset_without_a_key_falls_back_to_ollama, test_local_preset_needs_no_key

## `tests/conftest.py`
- Purpose: no header comment; read the file
- Defines: sample_vault, storage, network_open

## `tests/core/test_account.py`
- Purpose: no header comment; read the file
- Defines: Keychain, keychain, session, test_sign_in_saves_the_key_and_status_never_returns_it, test_sign_in_rejects_an_empty_key, test_sign_out_removes_the_key, test_keychain_failure_is_a_plain_error, test_remove_data_deletes_the_index_and_the_key_but_not_the_vault

## `tests/core/test_added_agents.py`
- Purpose: no header comment; read the file
- Defines: test_saved_agents_survive_a_new_session, test_no_file_lists_no_agents, test_save_rejects_a_list_without_ids, test_save_rejects_a_non_list

## `tests/core/test_cache_safety.py`
- Purpose: Deleting or damaging the index must always be safe: it is rebuilt from the vault.
- Defines: build, sidecars, test_deleted_files_reopen_cleanly, test_missing_storage_folder_is_created, test_corrupt_file_is_logged_deleted_and_rebuilt, test_schema_version_mismatch_rebuilds, test_index_for_a_different_vault_rebuilds, test_unrelated_sqlite_file_rebuilds, test_deleted_while_open_is_detected, test_deleting_the_index_rebuilds_an_identical_one

## `tests/core/test_cards.py`
- Purpose: no header comment; read the file
- Defines: test_created_card_survives_a_new_store, test_card_outlives_the_agent_that_made_it, test_locked_card_refuses_agent_changes, test_owner_can_change_and_unlock, test_agent_cannot_lock, test_bad_title_is_refused, test_unknown_or_unsafe_id_is_refused

## `tests/core/test_chat_history_provider.py`
- Purpose: no header comment; read the file
- Defines: Recorder, test_saved_chat_turns_reach_a_non_claude_provider

## `tests/core/test_cli.py`
- Purpose: no header comment; read the file
- Defines: run_core, has_note, test_default_storage_is_under_the_project, test_index, test_index_missing_vault, test_watch, test_keychain_error_is_reported_not_raised

## `tests/core/test_control.py`
- Purpose: Tests for the control panel backend: network, budgets, activity, memory, jobs, helpers, keys.
- Defines: Scripted, chat, test_off_blocks_a_model_call_before_anything_leaves, test_only_converse_and_open_allow_model_calls, test_network_mode_defaults_to_converse_and_is_saved, test_a_tiny_cap_pauses_the_next_request_and_allowance_lets_one_through, test_budget_windows_and_scopes, test_five_hour_window_is_rolling, test_budget_caps_are_saved_and_read_back, test_approvals_and_outcomes_are_logged_without_note_text, test_errors_reach_the_log, test_waiting_questions_are_listed_and_answering_clears_them, test_long_memory_moves_its_oldest_sections_to_an_archive, test_short_or_non_memory_notes_are_left_alone, test_opening_a_vault_trims_long_memory_notes

## `tests/core/test_inbox.py`
- Purpose: no header comment; read the file
- Defines: _write, test_pending_messages_stay_in_view_past_the_cap

## `tests/core/test_indexer.py`
- Purpose: no header comment; read the file
- Defines: indexer, bump, test_index_lives_under_storage_only, test_full_index_matches_manifest, test_second_sync_reads_nothing, test_touch_without_change_updates_stat_only, test_offline_edit_add_and_delete, test_apply_changes_for_files, test_apply_changes_ignores_paths_outside_vault, test_folder_moved_out_and_back_in, test_parse_failure_is_logged_and_others_continue, test_2000_notes_index_quickly

## `tests/core/test_parser.py`
- Purpose: no header comment; read the file
- Defines: link_keys, tag_keys, test_plain_link, test_alias_heading_embed_and_line, test_escaped_pipe_in_table, test_same_note_heading_link_is_skipped, test_duplicate_links_are_kept, test_code_and_comments_are_ignored, test_text_after_code_block_still_counts, test_inline_tags, test_inline_tags_dedupe_case_insensitively_keeping_first_spelling, test_frontmatter_tags, test_frontmatter_and_inline_tags_are_both_kept, test_non_string_frontmatter_tags_are_skipped, test_frontmatter_text_is_not_parsed_as_body

## `tests/core/test_read.py`
- Purpose: no header comment; read the file
- Defines: session, test_read_returns_the_note_text, test_read_refuses_paths_outside_the_vault, test_read_needs_an_open_vault

## `tests/core/test_scanner.py`
- Purpose: no header comment; read the file
- Defines: write, paths, test_finds_markdown_recursively_in_sorted_order, test_skips_hidden_files_and_folders, test_reports_stat_fields, test_symlink_outside_vault_is_skipped, test_size_limit, test_stat_note_rejects_paths_outside_and_ignored, test_non_utf8_is_logged_and_replaced, test_read_vanished_file_returns_none

## `tests/core/test_serve_chat.py`
- Purpose: no header comment; read the file
- Defines: Scripted, feed, run_serve, answers, wait_for, test_chat_answers_and_stays_out_of_the_way_of_graph, test_write_needs_confirm_through_the_protocol, test_stop_halts_a_running_chat, test_chat_needs_text_and_confirm_needs_a_waiting_call, test_answer_needs_a_waiting_question

## `tests/core/test_settings.py`
- Purpose: no header comment; read the file
- Defines: test_missing_file_gives_defaults, test_vault_path_is_relative_to_the_repo_root, test_unknown_settings_version_is_an_error, test_repo_settings_file_has_no_secret_field, test_env_vault_overrides_the_file, test_provider_defaults_to_claude_and_rejects_unknown_names, test_save_vault_writes_the_path_and_keeps_other_sections

## `tests/core/test_sidecar.py`
- Purpose: no header comment; read the file
- Defines: run_core, test_version_flag, test_serve_announces_ready_and_exits_on_stdin_eof, test_command_is_required, serve_with, test_serve_answers_graph_for_the_vault_it_was_given, test_serve_opens_a_vault_on_request, test_serve_graph_without_a_vault_is_an_error_not_a_crash, test_bad_json_gets_an_error_line_and_the_loop_keeps_going, test_open_rejects_a_missing_folder, test_serve_reads_the_settings_file_it_is_given

## `tests/core/test_store.py`
- Purpose: no header comment; read the file
- Defines: store, put, test_index_path_is_per_vault_under_storage, test_new_index_has_schema_and_meta, test_upsert_replaces_links_and_tags, test_delete_cascades, test_links_resolve_when_target_appears_and_dangle_when_it_goes, test_duplicate_names_prefer_path_match_then_shortest_path, test_heading_and_alias_links_resolve, test_update_stat, test_failed_transaction_rolls_back, test_reopen_keeps_current_index, test_view_has_no_subquery_or_star, test_old_sqlite_is_rejected, test_supported_sqlite_is_accepted

## `tests/core/test_system_stats.py`
- Purpose: no header comment; read the file
- Defines: test_cpu_percent_is_the_busy_share_between_two_samples, test_swap_percent_is_used_swap_and_zero_without_swap, test_read_gives_percentages_in_range_and_disk_free_in_gb, test_serve_answers_system_with_the_three_numbers

## `tests/core/test_tool_allowlist.py`
- Purpose: no header comment; read the file
- Defines: test_allowlist_round_trips_through_the_settings_file, test_bad_tool_names_are_refused, test_session_sets_and_lists_the_allowlist, test_session_refuses_a_bad_set_tools_request

## `tests/core/test_tool_limit.py`
- Purpose: no header comment; read the file
- Defines: Steps, _calls, _session, test_chat_pauses_at_the_tool_limit_and_continue_resumes, test_calls_past_the_limit_are_not_run, test_continue_needs_a_paused_request, test_max_tool_calls_comes_from_config

## `tests/core/test_watcher.py`
- Purpose: no header comment; read the file
- Defines: anyio_backend, indexer, watching, eventually, test_initial_sync_runs_when_watching_starts, test_live_edit, test_creating_a_note_fixes_dangling_links, test_delete, test_rename, test_atomic_save, test_folder_created_with_notes, test_burst_of_edits, test_index_deleted_while_watching_is_rebuilt, test_failed_batch_is_logged_and_watching_continues, test_stop_is_prompt

## `tests/core/test_webhooks.py`
- Purpose: no header comment; read the file
- Defines: session_at, test_webhooks_are_saved_listed_and_deleted, test_a_bad_webhook_request_is_refused, test_running_a_webhook_needs_approval_and_runs_its_job, test_a_webhook_file_with_an_unknown_kind_is_refused

## `tests/fixtures/__init__.py`
- Purpose: no header comment; read the file
- Defines: (none at top level)

## `tests/fixtures/make_sample_vault.py`
- Purpose: Generate a deterministic sample vault, plus a manifest of what the index should hold.
- Defines: _name_key, generate, main

## `tests/tools/conftest.py`
- Purpose: no header comment; read the file
- Defines: vault, indexer, lock

## `tests/tools/test_agent.py`
- Purpose: no header comment; read the file
- Defines: Scripted, make_agent, write_tool, read_tool, ask, test_read_tools_run_without_confirmation, test_write_waits_for_approval_and_shows_the_preview, test_declined_write_does_not_run, test_kill_switch_stops_a_pending_confirmation_within_a_second, test_kill_switch_stops_a_slow_model_call_within_a_second, test_kill_switch_is_checked_before_a_tool_runs, test_tool_errors_go_back_to_the_model, test_unknown_tool_and_step_limit, test_provider_failure_propagates, test_gate_decide_only_answers_open_calls

## `tests/tools/test_vault_tools.py`
- Purpose: no header comment; read the file
- Defines: tools, test_read_tools_are_read_tier, test_search_matches_title_and_path, test_read_note_returns_the_text, test_paths_must_stay_inside_the_vault, test_create_preview_shows_the_exact_change, test_create_note_writes_and_indexes, test_create_note_never_overwrites, test_memory_content_merges_into_existing_frontmatter, test_memory_content_keeps_existing_tags, test_move_note_moves_and_lists_folders, test_move_note_refuses_hubs_and_overwrites, test_set_status_moves_the_tag_first_and_clears_it, test_delete_tools_refuse_main_and_its_linked_notes

## `tools/__init__.py`
- Purpose: Assistant tools: the registry, the confirm gate and the kill switch.
- Defines: (none at top level)

## `tools/gate.py`
- Purpose: The kill switch and the confirm gate. Both are shared between threads.
- Defines: Stopped, KillSwitch, ConfirmGate, AskQueue

## `tools/registry.py`
- Purpose: A tool is a named action the model may ask for, with a safety tier.
- Defines: Tool, needs_confirm

## `tools/vault_tools.py`
- Purpose: The vault tools: search, read, create, edit and delete notes. Every path must stay inside the vault.
- Defines: is_hub_stem, main_guard, with_status, memory_content, vault_tools

