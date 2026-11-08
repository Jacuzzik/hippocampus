<!-- The right-panel tab for a selected added agent, laid out as in Thalha's picture: segmented pill groups, selected in accent. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onDestroy, onMount } from "svelte";
  import { Terminal } from "@xterm/xterm";
  import { FitAddon } from "@xterm/addon-fit";
  import "@xterm/xterm/css/xterm.css";
  import { startEdit, type SavedAgent } from "./addedAgents.svelte";
  import { createTerminalQueue } from "../regions/terminalQueue.svelte";

  let { agent }: { agent: SavedAgent } = $props();

  // The app does not report a status or usage for an added agent yet, so these show a dash, not made-up numbers.
  const NO_DATA = "—";

  let text = $state("");
  let error = $state<string | null>(null);
  let fontSize = $state(12);
  // Real state from the sidecar: set when the CLI starts, and when it exits.
  let runState = $state<"starting" | "running" | "exited" | "failed">("starting");
  let exitCode = $state<number | null>(null);
  const stateLabel = $derived(
    runState === "running"
      ? `running · pty ${agent.id.slice(0, 8)}`
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

  // The live terminal: the agent's own CLI in a real pseudo-terminal, drawn by xterm.js.
  let screen: HTMLDivElement;
  let term: Terminal | null = null;
  let fit: FitAddon | null = null;
  let unlisten: (() => void) | null = null;
  let observer: ResizeObserver | null = null;

  function sendSize(): void {
    if (!term || !fit) return;
    fit.fit();
    invoke("sidecar_call", {
      method: "terminal_resize",
      params: { agent: agent.id, rows: term.rows, cols: term.cols },
    }).catch(() => {});
  }

  async function startTerminal(): Promise<void> {
    term = new Terminal({
      fontFamily: "JetBrains Mono, monospace",
      fontSize: 12,
      cursorBlink: true,
      convertEol: true,
      theme: { background: getComputedStyle(document.documentElement).getPropertyValue("--color-md-bg-0").trim() || "#222229", foreground: "#e8e8e8", cursor: "#e8e8e8" },
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(screen);
    term.onData((data) => {
      invoke("sidecar_call", { method: "terminal_input", params: { agent: agent.id, data } }).catch((cause) =>
        console.error("Could not send to the terminal", cause),
      );
    });
    unlisten = await listen<{ event?: string; agent?: string; data?: string; exit?: number }>("sidecar-event", (event) => {
      if (event.payload.event !== "terminal" || event.payload.agent !== agent.id || !term) return;
      if (event.payload.data !== undefined) {
        term.write(event.payload.data);
        queue.output(event.payload.data);
      }
      if (event.payload.exit !== undefined) {
        term.write(`\r\n[the terminal closed, exit ${event.payload.exit}]\r\n`);
        runState = "exited";
        exitCode = event.payload.exit;
      }
    });
    // Wait until a drag settles before telling the CLI its new size, so it is not sent on every frame.
    let settle: ReturnType<typeof setTimeout> | undefined;
    observer = new ResizeObserver(() => {
      clearTimeout(settle);
      settle = setTimeout(sendSize, 200);
    });
    observer.observe(screen);
    fit.fit();
    try {
      const started = await invoke<{ replay?: string }>("sidecar_call", {
        method: "terminal_start",
        params: { agent: agent.id, provider: agent.provider, model: agent.model, folder: agent.folder, rows: term.rows, cols: term.cols },
      });
      // A reopened terminal shows the output it had on screen.
      if (started?.replay) term.write(started.replay);
      runState = "running";
    } catch (cause) {
      runState = "failed";
      term.write(`${String(cause)}\r\n`);
    }
  }

  // The − and + buttons change the text size; the terminal redraws and tells the CLI its new size.
  $effect(() => {
    const size = fontSize; // read before the early return, so the effect tracks it from the start
    if (!term) return;
    term.options.fontSize = size;
    sendSize();
  });

  let view = $state<"terminal" | "git" | "messages" | "traces">("terminal");
  let note = $state("");
  let gitText = $state("");

  // Steer sends the note into the agent's terminal, as if typed there.
  function steer(): void {
    const text = note.trim();
    if (!text) return;
    queue.send(text);
    note = "";
  }

  function showGit(): void {
    view = "git";
    invoke<{ text: string }>("sidecar_call", { method: "git_status", params: { folder: agent.folder } })
      .then((result) => (gitText = result.text))
      .catch((cause) => (gitText = String(cause)));
  }

  // Opens the agent's folder in the file manager, or in VS Code when app is "ide".
  function openFolder(app: "file" | "ide"): void {
    invoke("sidecar_call", { method: "open_folder", params: { folder: agent.folder, app } }).catch((cause) => {
      error = String(cause);
    });
  }

  onMount(() => {
    startTerminal();
  });

  onDestroy(() => {
    observer?.disconnect();
    unlisten?.();
    term?.dispose();
    // Leaving the tab does not stop the CLI: it keeps running in the sidecar. The Stop button does.
  });

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
    <button type="button" onclick={() => startEdit(agent.id, "rename")}>Edit</button>
    <button type="button" onclick={() => openFolder("file")} disabled={!agent.folder}>Open</button>
    <button type="button" onclick={() => openFolder("ide")} disabled={!agent.folder}>IDE</button>
  </div>
  <div class="seg" role="group" aria-label="Run controls">
    <button type="button" class="stop" onclick={() => invoke("sidecar_call", { method: "terminal_stop", params: { agent: agent.id } }).catch(() => {})}>Stop</button>
  </div>

  <div class="live">
    <span class="dot" aria-hidden="true"></span>
    <span>{stateLabel}</span>
    <span class="size"><button type="button" aria-label="Smaller text" onclick={() => (fontSize = Math.max(9, fontSize - 1))}>−</button><output>{fontSize}px</output><button type="button" aria-label="Larger text" onclick={() => (fontSize = Math.min(18, fontSize + 1))}>+</button></span>
  </div>

  <div class="seg" role="tablist" aria-label="Agent views">
    <button type="button" role="tab" aria-selected={view === "terminal"} class:on={view === "terminal"} onclick={() => (view = "terminal")}>Terminal</button>
    <button type="button" role="tab" aria-selected={view === "git"} class:on={view === "git"} onclick={() => showGit()}>Git</button>
    <button type="button" role="tab" aria-selected={view === "messages"} class:on={view === "messages"} onclick={() => (view = "messages")}>Messages</button>
    <button type="button" role="tab" aria-selected={view === "traces"} class:on={view === "traces"} onclick={() => (view = "traces")}>Traces</button>
  </div>

  <div class="screen" bind:this={screen} aria-label="Terminal for {agent.name}" hidden={view !== "terminal"}></div>
  {#if view === "git"}
    <pre class="git" aria-label="Git status">{gitText}</pre>
  {/if}
  {#if view === "messages"}
    <div class="placeholder-list" aria-label="Messages placeholders">
      <div class="row"><span class="key">FROM</span><span class="val">{NO_DATA}</span></div>
      <div class="row"><span class="key">TO</span><span class="val">{NO_DATA}</span></div>
      <div class="row"><span class="key">REPLY</span><span class="val">{NO_DATA}</span></div>
    </div>
  {/if}
  {#if view === "traces"}
    <div class="placeholder-list" aria-label="Traces placeholders">
      <div class="row"><span class="key">TOOL</span><span class="val">{NO_DATA}</span></div>
      <div class="row"><span class="key">TOKENS</span><span class="val">{NO_DATA}</span></div>
      <div class="row"><span class="key">TIME</span><span class="val">{NO_DATA}</span></div>
    </div>
  {/if}

  <div class="note-box">
    <textarea rows="2" bind:value={note} placeholder={`Note for ${agent.name}`} aria-label="Note for {agent.name}"></textarea>
    <button type="button" class="pill-on" disabled={!note.trim()} onclick={steer}>steer</button>
  </div>

  <p class="queue-label">Queue</p>
  {#if queue.items.length > 0}
    <div class="queued" aria-label="Queued messages">
      {#each queue.items as item, index (index)}
        <p>{index + 1}. {item}</p>
      {/each}
    </div>
  {/if}
  <form class="composer" onsubmit={send}>
    <textarea rows="3" bind:value={text} placeholder={`Message ${agent.name}`} aria-label={`Message ${agent.name}`}
      onkeydown={(e) => {
        // Enter sends; Shift+Enter starts a new line.
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          if (text.trim()) e.currentTarget.form?.requestSubmit();
        }
      }}></textarea>
    <button type="submit" class="send" disabled={!text.trim()}>Send →</button>
  </form>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  <ul class="todo-list" aria-label="Coming next">
    <li>Block tools</li>
    <li>1:1 run</li>
    <li>voice</li>
    <li>+ files</li>
    <li>+ folder</li>
  </ul>

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
    font-family: var(--font-mono);
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
    font-size: 14px;
    letter-spacing: 0.04em;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-md-accent);
  }
  .desc,
  .note-box {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    min-height: 36px;
    padding: 0 var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text-muted);
  }
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
  .note-box textarea {
    flex: 1;
    min-width: 0;
    min-height: 0;
    height: 36px;
    /* One line of text, centred vertically by matching the line height to the field height. */
    line-height: 36px;
    padding: 0;
    border: none;
    background: transparent;
    resize: none;
  }
  /* Segmented pill groups: one bordered pill, the selected segment in accent. */
  /* Placeholder rows, styled like the bottom-bar cards (AgentBar .chip.main .row). */
  .placeholder-list {
    display: grid;
    gap: 2px;
    padding: var(--space-2) 0;
    font-size: 11px;
    line-height: 1.6;
  }
  .placeholder-list .row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .placeholder-list .key {
    width: 44px;
    flex: none;
    font-size: 8px;
    color: var(--color-md-card-muted);
  }
  .placeholder-list .val {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .todo-list {
    margin: 0;
    padding: var(--space-2) 0 var(--space-2) var(--space-4);
    font-size: 11px;
    line-height: 1.6;
    color: var(--color-md-text-muted);
  }
  .seg {
    display: flex;
    align-items: stretch;
    border: 1px solid var(--color-md-border);
    border-radius: 999px;
    overflow: hidden;
  }
  .seg > * {
    flex: 1;
    min-height: 32px;
    font-family: var(--font-mono);
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
  .seg .stop {
    background: var(--color-danger);
    color: var(--color-md-accent-on);
  }
  /* The text-size pill, as on the main agent: − | 12px | +. */
  .size {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: 999px;
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
  .pill-on {
    border: none;
    border-radius: 999px;
    padding: 0 var(--space-2);
    min-height: 26px;
    background: var(--color-md-accent);
    color: var(--color-md-accent-on);
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
    border-radius: var(--radius-sm);
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
  /* The message text sits a little higher, as in the picture. */
  .composer textarea {
    padding-top: var(--space-1);
  }
  /* Dimmed until there is a message, as on the main agent. */
  .send:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .send {
    width: 100%;
    min-height: 32px;
    border-radius: 999px;
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
    color: var(--color-md-text-muted);
    font-size: 10px;
    text-transform: uppercase;
  }
  .screen {
    flex: 1 1 0;
    min-height: 300px;
    overflow: hidden;
    padding: var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-bg-0);
  }
  .error {
    margin: 0;
    color: var(--color-danger);
  }
</style>
