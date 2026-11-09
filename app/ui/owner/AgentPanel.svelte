<!-- The right-panel tab for a selected added agent, laid out as in Thalha's picture: segmented pill groups, selected in accent. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onDestroy, onMount } from "svelte";
  import { bootTask } from "./bootTasks.svelte.ts";
  import { Terminal } from "@xterm/xterm";
  import { FitAddon } from "@xterm/addon-fit";
  import "@xterm/xterm/css/xterm.css";
  import type { SavedAgent } from "./addedAgents.svelte";
  import { createTerminalQueue } from "../regions/terminalQueue.svelte";

  let { agent }: { agent: SavedAgent } = $props();

  // The app does not report a status or usage for an added agent yet, so these show a dash, not made-up numbers.
  const NO_DATA = "—";

  let text = $state("");
  let error = $state<string | null>(null);
  let fontSize = $state(12);
  // Real state from the sidecar: set when the CLI starts, and when it exits.
  let runState = $state<"starting" | "running" | "exited" | "stopped" | "failed">("starting");
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

  // The live terminal: the agent's own CLI in a real pseudo-terminal, drawn by xterm.js.
  let screen: HTMLDivElement;
  let term: Terminal | null = null;
  let fit: FitAddon | null = null;
  let unlisten: (() => void) | null = null;
  let observer: ResizeObserver | null = null;
  function sendSize(): void {
    if (!term || !fit) return;
    // A hidden or mid-animation panel reports a tiny width; telling the CLI that makes it redraw one or two characters per line.
    if (screen.clientWidth < 200 || screen.clientHeight < 80) return;
    fit.fit();
    invoke("sidecar_call", {
      method: "terminal_resize",
      params: { agent: agent.id, rows: term.rows, cols: term.cols },
    }).catch(() => {});
  }

  // "Block tools": on, the CLI runs without shell, file writes or web (Claude Code and Codex only).
  let blocked = $state(false);
  let fileInput: HTMLInputElement | undefined = $state();
  // A block change is a new session: stop the running CLI, then start it again with the new setting.
  async function toggleBlock(): Promise<void> {
    blocked = !blocked;
    await invoke("sidecar_call", { method: "terminal_stop", params: { agent: agent.id } }).catch(() => undefined);
    // Drop the old screen and listeners first, or the output would be drawn twice.
    unlisten?.();
    observer?.disconnect();
    term?.dispose();
    await startTerminal();
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
    queue.send(`Attached file: ${file.name}\n\`\`\`\n${await file.text()}\n\`\`\``);
  }

  async function startTerminal(): Promise<void> {
    const fgColour = getComputedStyle(document.documentElement).getPropertyValue("--color-fg").trim() || "#DADADA";
    term = new Terminal({
      fontFamily: "JetBrains Mono, monospace",
      fontSize: 12,
      cursorBlink: true,
      convertEol: true,
      theme: { background: getComputedStyle(document.documentElement).getPropertyValue("--color-md-bg-0").trim() || "#222229", foreground: fgColour, cursor: fgColour },
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(screen);
    term.onData((data) => {
      invoke("sidecar_call", { method: "terminal_input", params: { agent: agent.id, data } }).catch((cause) =>
        console.error("Could not send to the terminal", cause),
      );
    });
    unlisten = await listen<{ event?: string; agent?: string; data?: string; exit?: number; stopped?: boolean }>("sidecar-event", (event) => {
      if (event.payload.event !== "terminal" || event.payload.agent !== agent.id || !term) return;
      if (event.payload.data !== undefined) {
        // While the saved screen is being written, live output waits behind it, so the replay is not drawn over the new output.
        term.write(event.payload.data);
        queue.output(event.payload.data);
      }
      if (event.payload.exit !== undefined) {
        term.write(event.payload.stopped ? "\r\n[the terminal was stopped]\r\n" : `\r\n[the terminal closed, exit ${event.payload.exit}]\r\n`);
        runState = event.payload.stopped ? "stopped" : "exited";
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
        params: { agent: agent.id, provider: agent.provider, model: agent.model, folder: agent.folder, rows: term.rows, cols: term.cols, block_tools: blocked },
      });
      // A reopened terminal shows the output it had on screen.
      // reset() clears modes left by the old screen (alt buffer, cursor, colours) so the replay draws cleanly, as the main terminal does.
      if (started?.replay) {
        term.reset();
        term.write(started.replay);
      }
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
  let gitText = $state("");

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
    // Counted as start-up work so the loading screen waits for this terminal.
    const done = bootTask();
    startTerminal().finally(done);
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
    <button type="button" onclick={() => openFolder("ide")} disabled={!agent.folder}>IDE</button>
  </div>
  <div class="seg" role="group" aria-label="Run controls">
    <button type="button" class="stop" title="Interrupts the current run" disabled={runState !== "running"} onclick={() => invoke("sidecar_call", { method: "terminal_input", params: { agent: agent.id, data: "\x1b" } }).catch(() => {})}>Stop</button>
    <button type="button" aria-pressed={blocked} class:on={blocked} onclick={toggleBlock}>block tools</button>
  </div>


  {#if view !== "git"}
    <div class="seg" role="tablist" aria-label="Agent views">
      <button type="button" role="tab" aria-selected={view === "terminal"} class:on={view === "terminal"} onclick={() => (view = "terminal")}>Terminal</button>
      <button type="button" role="tab" aria-selected="false" disabled={!agent.folder} onclick={() => showGit()}>Git</button>
      <button type="button" role="tab" aria-selected={view === "messages"} class:on={view === "messages"} onclick={() => (view = "messages")}>Messages</button>
      <button type="button" role="tab" aria-selected={view === "traces"} class:on={view === "traces"} onclick={() => (view = "traces")}>Traces</button>
    </div>
  {/if}

  <div class="live">
    <span class="dot" aria-hidden="true"></span>
    <span>{stateLabel}</span>
    <span class="size"><button type="button" aria-label="Smaller text" onclick={() => (fontSize = Math.max(9, fontSize - 1))}>−</button><output>{fontSize}px</output><button type="button" aria-label="Larger text" onclick={() => (fontSize = Math.min(18, fontSize + 1))}>+</button></span>
  </div>

  <div class="screen" bind:this={screen} aria-label="Terminal for {agent.name}" hidden={view !== "terminal"}></div>
  {#if view === "git"}
    <button type="button" class="back" onclick={() => (view = "terminal")}>← back to terminal</button>
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
    <textarea rows="2" bind:value={text} placeholder={`Message ${agent.name}`} aria-label={`Message ${agent.name}`}
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
      <input bind:this={fileInput} type="file" accept=".txt,.md,.csv,.json,.ts,.js,.py,.svelte,.css,.html" onchange={attachFile} hidden />
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
  .placeholder-list {
    display: grid;
    gap: 2px;
    padding: var(--space-2) 0;
    font-size: var(--font-size-xs);
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
    font-size: var(--font-size-tag);
    color: var(--color-md-card-muted);
  }
  .placeholder-list .val {
    overflow: hidden;
    text-overflow: ellipsis;
  }
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
  /* The frame is an inset shadow, not a border: xterm's fit sizes the terminal from the box's height and width
     and ignores borders, so a border made the last row and the right edge run out of the box. */
  .screen {
    flex: 1 1 0;
    min-height: 0;
    overflow: hidden;
    padding: var(--space-1);
    box-shadow: inset 0 0 0 1px var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-bg-0);
  }
  .error {
    margin: 0;
    color: var(--color-danger);
  }
</style>
