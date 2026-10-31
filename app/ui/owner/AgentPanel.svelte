<!-- The right-panel tab for a selected added agent, laid out as in the agreed picture: header, controls, note, tabs, terminal, stats, queue. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onDestroy, onMount } from "svelte";
  import { Terminal } from "@xterm/xterm";
  import { FitAddon } from "@xterm/addon-fit";
  import "@xterm/xterm/css/xterm.css";
  import { removeAgent, selection, startEdit, type SavedAgent } from "./addedAgents.svelte";

  let { agent }: { agent: SavedAgent } = $props();

  // The app does not report a status or usage for an added agent yet, so these show a dash, not made-up numbers.
  const NOT_REPORTED = "Not reported";
  const NO_DATA = "—";

  let text = $state("");
  let error = $state<string | null>(null);

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
      theme: { background: "#111111", foreground: "#e8e8e8", cursor: "#e8e8e8" },
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
      if (event.payload.data !== undefined) term.write(event.payload.data);
      if (event.payload.exit !== undefined) term.write(`\r\n[the terminal closed, exit ${event.payload.exit}]\r\n`);
    });
    observer = new ResizeObserver(() => sendSize());
    observer.observe(screen);
    fit.fit();
    try {
      await invoke("sidecar_call", {
        method: "terminal_start",
        params: { agent: agent.id, provider: agent.provider, rows: term.rows, cols: term.cols },
      });
    } catch (cause) {
      term.write(`${String(cause)}\r\n`);
    }
  }

  onMount(() => {
    startTerminal();
  });

  onDestroy(() => {
    observer?.disconnect();
    unlisten?.();
    term?.dispose();
    // The CLI's session is kept by the sidecar, so the next open resumes it.
    invoke("sidecar_call", { method: "terminal_stop", params: { agent: agent.id } }).catch(() => {});
  });

  // The queue sends the message into the agent's terminal, as if typed there.
  async function send(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    text = "";
    error = null;
    try {
      await invoke("sidecar_call", {
        method: "terminal_input",
        params: { agent: agent.id, data: `${trimmed}\r` },
      });
    } catch (cause) {
      error = String(cause);
    }
  }
</script>

<div class="agent-panel">
  <header>
    <div class="title">
      <b>{agent.name}</b>
      <span class="status">{NOT_REPORTED}</span>
      <span class="branch">{agent.description || NO_DATA}</span>
    </div>
    <div class="icons">
      {#if agent.id !== "hippo"}<button type="button" onclick={() => startEdit(agent.id, "rename")}>Edit</button>{/if}
      {#if agent.id === "hippo"}
        <button type="button">auto</button>
        <button type="button">IDE</button>
      {:else}
        <button type="button">IDE</button>
        <button type="button">Open</button>
        <button type="button" class="close" aria-label="Close panel" onclick={() => (selection.id = null)}>×</button>
      {/if}
    </div>
  </header>

  <!-- Dummy controls: they do nothing until their behaviour is decided. -->
  <div class="controls">
    <button type="button">Block tools</button>
    <button type="button" class="stop">Stop after this step</button>
    <button type="button">▶ 1:1</button>
  </div>

  <div class="note-row">
    <input type="text" placeholder="send this agent a note… (arrives as context on its next turn)" aria-label="Note for {agent.name}" />
    <button type="button">steer</button>
  </div>

  <div class="tabs" role="group" aria-label="Agent views">
    <button type="button" class="on" aria-pressed="true">Terminal</button>
    <button type="button" aria-pressed="false">Git</button>
    <button type="button" aria-pressed="false">Messages</button>
    <button type="button" aria-pressed="false">Traces</button>
  </div>

  <div class="live">
    <span>● live · pty {agent.id.slice(0, 8)}</span>
    <span class="size"><button type="button">−</button> 12px <button type="button">+</button></span>
  </div>

  <div class="screen" bind:this={screen} aria-label="Terminal for {agent.name}"></div>

  <dl class="stats">
    <div><dt>Cost</dt><dd>{NO_DATA}</dd></div>
    <div><dt>Tokens</dt><dd>{NO_DATA}</dd></div>
    <div><dt>Agent time</dt><dd>{NO_DATA}</dd></div>
    <div><dt>Context</dt><dd>{NO_DATA}</dd></div>
  </dl>

  <p class="queue-label">QUEUE</p>
  <form class="composer" onsubmit={send}>
    <textarea rows="3" bind:value={text} placeholder={`Message ${agent.name}`} aria-label={`Message ${agent.name}`}></textarea>
    <button type="submit" class="send" disabled={!text.trim()}>Send →</button>
  </form>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  <!-- Dummy attachment buttons: they do nothing until their behaviour is decided. -->
  <div class="bar">
    <span class="hint">Press and hold Alt</span>
    <button type="button">voice</button>
    <button type="button">+ files</button>
    <button type="button">+ folder</button>
  </div>

  <div class="actions">
    {#if agent.id !== "hippo"}
      <button type="button" onclick={() => startEdit(agent.id, "note")}>Add note</button>
      <button type="button" class="danger" onclick={() => removeAgent(agent.id)}>Delete</button>
    {/if}
    {#if agent.note}<p class="note">{agent.note}</p>{/if}
  </div>
</div>

<style>
  .agent-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-2);
    color: var(--color-md-text);
    font-size: var(--font-size-xs);
  }
  header,
  .controls,
  .note-row,
  .tabs,
  .live,
  .icons,
  .actions,
  .composer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-1);
  }
  header {
    justify-content: space-between;
  }
  .title {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .title b {
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .status::before {
    content: "■ ";
  }
  .tabs button {
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.04em;
  }
  .tabs .on {
    background: var(--color-md-surface-raised, var(--color-md-surface));
  }
  .hint {
    margin-right: auto;
    color: var(--color-md-text-muted);
    font-size: 10px;
  }
  textarea {
    flex: 1;
    min-width: 0;
    min-height: 64px;
    padding: var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text);
    font: inherit;
    resize: vertical;
  }
  .status,
  .branch {
    padding: 0 var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    color: var(--color-md-text-muted);
  }
  button,
  input {
    min-height: 36px;
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
  .stop {
    border-color: var(--color-danger);
    background: var(--color-danger);
    color: var(--color-md-accent-on);
  }
  .danger,
  .close {
    color: var(--color-danger);
  }
  .note-row input,
  .composer input {
    flex: 1;
    min-width: 0;
  }
  .tabs .on {
    border-color: var(--color-md-text);
    border-bottom: 2px solid var(--color-md-accent);
  }
  .send {
    background: var(--color-md-accent);
    color: var(--color-md-accent-on);
    border-color: var(--color-md-accent);
  }
  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }
  .live {
    justify-content: space-between;
    color: var(--color-md-text-muted);
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-1);
    margin: 0;
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-md-border);
  }
  .stats dt {
    color: var(--color-md-text-muted);
    font-size: 10px;
  }
  .stats dd {
    margin: 0;
    font-size: 14px;
  }
  .queue-label {
    margin: 0;
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-md-border);
    color: var(--color-md-text-muted);
    font-size: 10px;
  }
  .actions {
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-md-border);
  }
  .screen {
    height: 420px;
    padding: var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: #111;
  }
  .error {
    margin: 0;
    color: var(--color-danger);
  }
  .note {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
</style>
