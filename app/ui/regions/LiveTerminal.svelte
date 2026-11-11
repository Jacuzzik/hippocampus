<!-- A real terminal: the agent's own CLI in a pseudo-terminal, drawn by xterm.js. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onDestroy, onMount } from "svelte";
  import { bootTask } from "../owner/bootTasks.svelte.ts";
  import { Terminal } from "@xterm/xterm";
  import { FitAddon } from "@xterm/addon-fit";
  import "@xterm/xterm/css/xterm.css";

  let { agentId, provider, fontSize = 12, onoutput }: { agentId: string; provider: string; fontSize?: number; onoutput?: (data: string) => void } = $props();

  let screen: HTMLDivElement;
  let term: Terminal | null = null;
  let fit: FitAddon | null = null;
  let unlisten: (() => void) | null = null;
  let observer: ResizeObserver | null = null;
  let restarting = false;
  let onEngineChangedHandler: ((e: Event) => void) | null = null;

  function sendSize(): void {
    if (!term || !fit) return;
    fit.fit();
    invoke("sidecar_call", {
      method: "terminal_resize",
      params: { agent: agentId, rows: term.rows, cols: term.cols },
    }).catch(() => {});
  }

  async function startTerminal(): Promise<void> {
    // The background is read from the app's dark token, so the terminal matches the panels.
    const bg = getComputedStyle(document.documentElement).getPropertyValue("--color-md-bg-0").trim() || "#222229";
    const fg = getComputedStyle(document.documentElement).getPropertyValue("--color-fg").trim() || "#DADADA";
    term = new Terminal({
      fontFamily: "JetBrains Mono, monospace",
      fontSize: 12,
      cursorBlink: true,
      convertEol: true,
      theme: { background: bg, foreground: fg, cursor: fg },
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(screen);
    term.onData((data) => {
      // Focus in/out reports are not typing; sent to the CLI they show as ^[[O text on screen.
      if (data === "\x1b[I" || data === "\x1b[O") return;
      invoke("sidecar_call", { method: "terminal_input", params: { agent: agentId, data } }).catch((cause) =>
        console.error("Could not send to the terminal", cause),
      );
    });
    unlisten = await listen<{ event?: string; agent?: string; data?: string; exit?: number; stopped?: boolean }>("sidecar-event", (event) => {
      if (event.payload.event !== "terminal" || event.payload.agent !== agentId || !term) return;
      if (event.payload.data !== undefined) {
        term.write(event.payload.data);
        onoutput?.(event.payload.data);
      }
      // A model change stops the old process on purpose; the new session replaces it, so no "closed" line.
      if (event.payload.exit !== undefined && !restarting) {
        term.write(event.payload.stopped ? "\r\n[the terminal was stopped]\r\n" : `\r\n[the terminal closed, exit ${event.payload.exit}]\r\n`);
      }
    });
    // A model change in the Monitor tab starts a fresh session in this same terminal.
    onEngineChangedHandler = (e: Event) => {
      const detail = (e as CustomEvent<{ provider?: string; model?: string }>).detail;
      const next = detail?.provider ?? provider;
      restarting = true;
      term?.reset();
      // After the new CLI starts, resend the size so it redraws at the right dimensions (fixes garbled output).
      startSession(next)
        .then(() => setTimeout(sendSize, 300))
        .finally(() => setTimeout(() => (restarting = false), 1500));
    };
    window.addEventListener("engine-changed", onEngineChangedHandler);
    // Wait until a drag settles before telling the CLI its new size.
    let settle: ReturnType<typeof setTimeout> | undefined;
    observer = new ResizeObserver(() => {
      clearTimeout(settle);
      settle = setTimeout(sendSize, 200);
    });
    observer.observe(screen);
    fit.fit();
    await startSession(provider);
  }

  // Starts the CLI for this provider. A reopened terminal shows the output it had on screen.
  async function startSession(p: string): Promise<void> {
    if (!term) return;
    try {
      const started = await invoke<{ replay?: string }>("sidecar_call", {
        method: "terminal_start",
        params: { agent: agentId, provider: p, rows: term.rows, cols: term.cols },
      });
      // reset() clears modes left by the old screen (alt buffer, cursor, colours) so the replay draws cleanly.
      if (started?.replay) {
        term.reset();
        term.write(started.replay);
      }
    } catch (cause) {
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

  onMount(() => {
    // Counted as start-up work so the loading screen waits for this terminal.
    const done = bootTask();
    startTerminal().finally(done);
  });

  onDestroy(() => {
    observer?.disconnect();
    unlisten?.();
    if (onEngineChangedHandler) window.removeEventListener("engine-changed", onEngineChangedHandler);
    term?.dispose();
    // Leave the CLI running: stopping it here sent SIGTERM on every reload (exit 143). The next open reattaches to it.
  });
</script>

<div class="screen" bind:this={screen} aria-label="Live terminal"></div>

<style>
  /* Fixed height and clipped: the terminal's own rows must not grow the box around it. */
  .screen {
    flex: 1 1 0;
    min-height: 0;
    overflow: hidden;
    padding: var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-bg-0);
  }
</style>
