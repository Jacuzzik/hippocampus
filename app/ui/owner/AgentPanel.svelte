<!-- The right-panel tab for a selected added agent, laid out as in Thalha's picture: segmented pill groups, selected in accent. -->
<script lang="ts">
  import { FONT_MAX, FONT_MIN, prefs } from "../prefs.svelte.ts";
  import Tabs from "../controls/Tabs.svelte";
  import EmptyState from "../controls/EmptyState.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { every } from "../poll.ts";
  import LiveTerminal, {
    type TerminalState,
  } from "../regions/LiveTerminal.svelte";
  import type { SavedAgent } from "./addedAgents.svelte";
  import { createTerminalQueue } from "../regions/terminalQueue.svelte";

  let { agent }: { agent: SavedAgent } = $props();

  // The app does not report a status or usage for an added agent yet, so these show a dash, not made-up numbers.
  const NO_DATA = "—";

  let text = $state("");
  let error = $state<string | null>(null);
  // One text size for every agent terminal, set here or in Settings > Appearance.
  const fontSize = $derived(prefs.terminalFontSize);
  // Real state from the sidecar: set when the CLI starts, and when it exits.
  let runState = $state<
    "starting" | "running" | "exited" | "stopped" | "failed"
  >("starting");
  let exitCode = $state<number | null>(null);
  const stateLabel = $derived(
    runState === "running"
      ? "running"
      : runState === "stopped"
        ? "stopped"
        : runState === "exited"
          ? `exited · code ${exitCode}`
          : runState === "failed"
            ? "not running"
            : "starting…",
  );

  // Messages wait here while the CLI is printing, then go into its terminal in order.
  const queue = createTerminalQueue(() => agent.id);
  $effect(() => {
    const timer = setInterval(queue.tick, 1000);
    return () => clearInterval(timer);
  });

  // The agent's CLI runs in the shared terminal. The panel is mounted hidden at launch, so the terminal
  // redraws at its first real size, and gives its bottom row back so the last line sits inside the box.
  let terminal: LiveTerminal | undefined = $state();
  function onTerminalState(state: TerminalState, code: number | null): void {
    runState = state;
    exitCode = code;
  }

  // "Block tools": on, the CLI runs without shell, file writes or web (Claude Code and Codex only).
  let blocked = $state(false);
  let fileInput: HTMLInputElement | undefined = $state();
  // A block change is a new session: stop the running CLI, then start it again with the new setting.
  // It ends the running session, so the button asks first.
  let confirmBlock = $state(false);
  async function toggleBlock(): Promise<void> {
    confirmBlock = false;
    blocked = !blocked;
    await invoke("sidecar_call", {
      method: "terminal_stop",
      params: { agent: agent.id },
    }).catch(() => undefined);
    await terminal?.restart();
  }

  // "+ files": a text file (up to 100 KB) goes into the agent's queue, as the Assistant does.
  async function attachFile(event: Event): Promise<void> {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    if (file.size > 100 * 1024) {
      error = `${file.name} is larger than 100 KB, so it was not attached.`;
      return;
    }
    queue.send(
      `Attached file: ${file.name}\n\`\`\`\n${await file.text()}\n\`\`\``,
    );
  }

  // "terminal", "git", "messages" or "traces".
  let view = $state("terminal");
  let gitText = $state("");
  const views = $derived([
    { id: "terminal", label: "Terminal" },
    {
      id: "git",
      label: "Git",
      disabled: !agent.folder,
      reason: "This agent has no working folder",
    },
    { id: "messages", label: "Messages" },
    { id: "traces", label: "Traces" },
  ]);

  // Messages and Traces read again every few seconds while their tab is open.
  type Message = {
    id: string;
    from: string | null;
    to: string | null;
    act: string | null;
    subject: string | null;
    created_at: string | null;
    state: string;
  };
  type Trace = {
    at: string | null;
    tool: string;
    detail: string;
    status: string;
  };
  let messages = $state<Message[]>([]);
  let traces = $state<Trace[]>([]);
  async function loadView(): Promise<void> {
    try {
      if (view === "messages") {
        const all = (
          await invoke<{ messages: Message[] }>("sidecar_call", {
            method: "inbox",
          })
        ).messages;
        messages = all.filter((m) => m.from === agent.id || m.to === agent.id);
      } else if (view === "traces") {
        traces = (
          await invoke<{ traces: Trace[] }>("sidecar_call", {
            method: "terminal_traces",
            params: { agent: agent.id },
          })
        ).traces;
      }
    } catch (cause) {
      error = String(cause);
    }
  }
  $effect(() => {
    if (view !== "messages" && view !== "traces") return;
    void loadView();
    return every(loadView, 5000);
  });

  function showGit(): void {
    gitText = "Reading git status…";
    invoke<{ text: string }>("sidecar_call", {
      method: "git_status",
      params: { folder: agent.folder },
    })
      .then((result) => (gitText = result.text))
      .catch((cause) => (gitText = String(cause)));
  }

  // Opens the agent's folder in the file manager, or in VS Code when app is "ide".
  function openFolder(app: "file" | "ide"): void {
    invoke("sidecar_call", {
      method: "open_folder",
      params: { folder: agent.folder, app },
    }).catch((cause) => {
      error = String(cause);
    });
  }

  // The queue sends the message into the agent's terminal, as if typed there.
  async function send(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    text = "";
    queue.send(trimmed);
  }
</script>

<div class="agent-panel">
  <header>
    <b>{agent.name}</b>
  </header>

  <div class="desc">{agent.description || NO_DATA}</div>

  <div class="seg" role="group" aria-label="Agent actions">
    <button
      type="button"
      onclick={() => openFolder("ide")}
      disabled={!agent.folder}
      title={agent.folder
        ? "Open this agent's folder in VS Code"
        : "This agent has no working folder"}>IDE</button
    >
  </div>
  <div class="seg" role="group" aria-label="Run controls">
    <button
      type="button"
      class="stop"
      title="Interrupts the current run"
      disabled={runState !== "running"}
      onclick={() =>
        invoke("sidecar_call", {
          method: "terminal_input",
          params: { agent: agent.id, data: "\x1b" },
        }).catch(() => {})}>Stop</button
    >
    <button
      type="button"
      aria-pressed={blocked}
      class:on={blocked}
      onclick={() => (confirmBlock = !confirmBlock)}>block tools</button
    >
  </div>
  {#if confirmBlock}
    <div class="confirm" role="group" aria-label="Confirm block tools">
      <p>
        {blocked ? "Give the tools back" : "Block shell, file writes and web"} for
        {agent.name}? Its program restarts, and work in progress stops.
      </p>
      <button type="button" class="send" onclick={toggleBlock}
        >Restart {blocked ? "with tools" : "without tools"}</button
      >
      <button type="button" onclick={() => (confirmBlock = false)}
        >Cancel</button
      >
    </div>
  {/if}

  <Tabs
    items={views}
    bind:value={view}
    label="Agent views"
    idBase={`agent-${agent.id.replace(/\W+/g, "-")}`}
    segmented
    onchange={(id) => id === "git" && showGit()}
  />

  <div class="live">
    <span class="dot" aria-hidden="true"></span>
    <span>{stateLabel}</span>
    <span class="size"
      ><button
        type="button"
        aria-label="Smaller text"
        disabled={fontSize <= FONT_MIN}
        onclick={() => (prefs.terminalFontSize -= 1)}>−</button
      ><output>{fontSize}px</output><button
        type="button"
        aria-label="Larger text"
        disabled={fontSize >= FONT_MAX}
        onclick={() => (prefs.terminalFontSize += 1)}>+</button
      ></span
    >
  </div>

  <LiveTerminal
    bind:this={terminal}
    agentId={agent.id}
    provider={agent.provider}
    model={agent.model}
    folder={agent.folder}
    blockTools={blocked}
    {fontSize}
    label={`Terminal for ${agent.name}`}
    hidden={view !== "terminal"}
    restore="redraw"
    trimRow
    onoutput={queue.output}
    onstate={onTerminalState}
  />
  {#if view === "git"}
    <pre class="git" aria-label="Git status">{gitText}</pre>
  {/if}
  {#if view === "messages"}
    {#if messages.length === 0}
      <EmptyState
        title="No messages yet"
        text="Messages this agent sends or receives show here. Write to it from the Inbox tab in the Control Room."
      />
    {:else}
      <ul class="rows" aria-label="Messages for {agent.name}">
        {#each messages as message (message.id + message.state)}
          <li>
            <span class="tag"
              >{message.state === "queued" ? "waiting" : message.state}</span
            >
            <span class="dim"
              >{message.from === agent.id
                ? `to ${message.to}`
                : `from ${message.from}`}</span
            >
            <span class="grow">{message.subject || message.act}</span>
            <small
              >{(message.created_at ?? "")
                .replace("T", " ")
                .slice(5, 16)}</small
            >
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
  {#if view === "traces"}
    {#if traces.length === 0}
      <EmptyState
        title="No tool calls yet"
        text="Every tool this agent runs shows here with its time and result, shell commands included. Only agents on Claude Code are read so far."
      />
    {:else}
      <ul class="rows" aria-label="Tool calls by {agent.name}">
        {#each traces as trace, index (index)}
          <li>
            <span class="tag" class:bad={trace.status === "failed"}
              >{trace.status}</span
            >
            <span class="dim">{trace.tool.replace("mcp__vault__", "")}</span>
            <span class="grow mono">{trace.detail}</span>
            <small>{(trace.at ?? "").replace("T", " ").slice(5, 16)}</small>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}

  <!-- Queue, message box, Send and + files sit in one composer, as on the main agent, so they share its gaps. -->
  <form class="composer" onsubmit={send}>
    <p class="queue-label">Queue</p>
    {#if queue.items.length > 0}
      <div class="queued" aria-label="Queued messages">
        {#each queue.items as item, index (index)}
          <p>{index + 1}. {item}</p>
        {/each}
      </div>
    {/if}
    <textarea
      rows="2"
      bind:value={text}
      placeholder={`Message ${agent.name}`}
      aria-label={`Message ${agent.name}`}
      onkeydown={(e) => {
        // Enter sends; Shift+Enter starts a new line.
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          if (text.trim()) e.currentTarget.form?.requestSubmit();
        }
      }}></textarea>
    <button type="submit" class="send" disabled={!text.trim()}>Send →</button>
    <div class="attach">
      <button type="button" onclick={() => fileInput?.click()}>+ files</button>
      <input
        bind:this={fileInput}
        type="file"
        accept=".txt,.md,.csv,.json,.ts,.js,.py,.svelte,.css,.html"
        onchange={attachFile}
        hidden
      />
    </div>
  </form>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</div>

<style>
  .agent-panel {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: 0;
    color: var(--color-md-text);
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
  }
  header,
  .live {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-1);
  }
  header b {
    font-size: var(--font-size-md);
    letter-spacing: 0.04em;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-md-accent);
  }
  .desc,
  /* A long description stays on one line and ends in "…" instead of wrapping. */
  .desc {
    display: block;
    padding-top: 8px;
    padding-bottom: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* The note is a one-line field inside its box; the shared textarea height would make the row too tall. */
  /* Segmented pill groups: one bordered pill, the selected segment in accent. */
  /* Placeholder rows, styled like the bottom-bar cards (AgentBar .chip.main .row). */
  .seg {
    display: flex;
    flex-wrap: wrap;
    align-items: stretch;
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }
  /* Tab and action buttons: the main agent's sizes (32px tall, 8px side padding, 1px dividers). */
  .seg > * {
    flex: 1 1 0;
    min-height: 32px;
    cursor: pointer;
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    padding: 0 var(--space-2);
    border: none;
    border-radius: 0;
    border-right: 1px solid var(--color-md-border);
    background: transparent;
    color: var(--color-md-text-muted);
    text-align: center;
    text-transform: lowercase;
    white-space: nowrap;
  }
  .seg > *:last-child {
    border-right: none;
  }
  .seg .on,
  .seg button:hover:not(:disabled):is(.on) {
    background: var(--color-md-accent);
    color: var(--color-md-accent-on);
  }
  .seg > *:disabled {
    cursor: default;
    opacity: 0.6;
  }
  /* Stop: transparent, with a red outline and red text while it can be pressed (as on the main agent). */
  .seg .stop {
    background: transparent;
    color: var(--color-md-text);
  }
  .stop:not(:disabled) {
    color: var(--color-danger);
    box-shadow: inset 0 0 0 1px var(--color-danger);
  }
  /* The text-size pill, as on the main agent: − | 12px | +. */
  .size {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }
  .size button {
    min-width: 36px;
    min-height: 32px;
    padding: 0;
    border: none;
    border-radius: 0;
    background: transparent;
    color: var(--color-md-text-muted);
  }
  .size output {
    min-width: 48px;
    text-align: center;
    border-left: 1px solid var(--color-md-border);
    border-right: 1px solid var(--color-md-border);
    color: var(--color-md-text-muted);
  }
  .live {
    justify-content: flex-start;
    color: var(--color-md-text-muted);
  }
  button,
  textarea {
    min-height: 32px;
    padding: 0 var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-md);
    background: var(--color-md-surface);
    color: var(--color-md-text);
    font: inherit;
  }
  button {
    cursor: pointer;
  }
  textarea {
    width: 100%;
    min-height: 64px;
    padding: var(--space-2);
    resize: vertical;
  }
  /* Send is a full-width accent bar under the message box, like the picture. */
  .composer {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  /* Disabled buttons look the same as on the main agent: dimmed, no pointer. */
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  /* Stop is red while it can be pressed, as on the main agent. */
  .stop:not(:disabled) {
    border-color: var(--color-danger);
    color: var(--color-danger);
  }
  /* Dimmed until there is a message, as on the main agent. */
  .send:disabled {
    opacity: 0.5;
    cursor: default;
  }
  /* + files sits full width under Send, centred, as on the main agent. */
  .attach {
    display: flex;
    justify-content: center;
  }
  .attach button {
    width: 100%;
    text-align: center;
  }
  .send {
    width: 100%;
    border-radius: var(--radius-md);
    background: var(--color-md-accent);
    color: var(--color-md-accent-on);
    border-color: var(--color-md-accent);
  }
  /* Only this box scrolls when several messages wait; the sidebar itself stays put. */
  .queued {
    max-height: 96px;
    overflow-y: auto;
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    color: var(--color-md-text-muted);
  }
  .queued p {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .queue-label {
    margin: 0 0 var(--space-1);
    font-family: var(--font-mono);
    color: var(--color-md-text-muted);
    font-size: var(--font-size-tag);
    text-transform: uppercase;
  }
  /* Git status sits in the same box as the terminal: fixed size, scrolls inside itself, so the tabs stay put. */
  .git {
    flex: 1 1 0;
    min-height: 0;
    margin: 0;
    overflow: auto;
    padding: var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-bg-0);
    color: var(--color-md-text);
    font-family: var(--font-mono);
    font-size: var(--font-size-tag);
    white-space: pre;
  }
  /* Messages and Traces: one row each, scrolling inside the same box the terminal uses. */
  .rows {
    flex: 1 1 0;
    min-height: 0;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    list-style: none;
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
  }
  .rows li {
    display: flex;
    gap: var(--space-2);
    align-items: baseline;
    padding: var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--color-md-border);
  }
  .rows .tag {
    color: var(--color-md-accent);
  }
  .rows .tag.bad {
    color: var(--color-danger);
  }
  .rows .dim,
  .rows small {
    flex: none;
    color: var(--color-md-text-muted);
  }
  .rows .grow {
    flex: 1 1 0;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .rows .mono {
    font-family: var(--font-mono);
  }
  .confirm {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    padding: var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
  }
  .confirm p {
    flex: 1 1 100%;
    margin: 0;
    color: var(--color-md-text-muted);
  }
  .confirm button {
    flex: 1 1 0;
    width: auto;
  }
  .error {
    margin: 0;
    color: var(--color-danger);
  }
</style>
