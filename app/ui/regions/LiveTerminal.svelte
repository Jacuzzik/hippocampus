<!-- A real terminal: the agent's own CLI in a pseudo-terminal, drawn by xterm.js. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onDestroy, onMount } from "svelte";
  import { Terminal } from "@xterm/xterm";
  import { FitAddon } from "@xterm/addon-fit";
  import "@xterm/xterm/css/xterm.css";

  let { agentId, provider, fontSize = 12, onoutput }: { agentId: string; provider: string; fontSize?: number; onoutput?: (data: string) => void } = $props();

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
      params: { agent: agentId, rows: term.rows, cols: term.cols },
    }).catch(() => {});
  }

  async function startTerminal(): Promise<void> {
    // The background is read from the app's dark token, so the terminal matches the panels.
    const bg = getComputedStyle(document.documentElement).getPropertyValue("--color-md-bg-0").trim() || "#222229";
    term = new Terminal({
      fontFamily: "JetBrains Mono, monospace",
      fontSize: 12,
      cursorBlink: true,
      convertEol: true,
      theme: { background: bg, foreground: "#e8e8e8", cursor: "#e8e8e8" },
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
    unlisten = await listen<{ event?: string; agent?: string; data?: string; exit?: number }>("sidecar-event", (event) => {
      if (event.payload.event !== "terminal" || event.payload.agent !== agentId || !term) return;
      if (event.payload.data !== undefined) {
        term.write(event.payload.data);
        onoutput?.(event.payload.data);
      }
      if (event.payload.exit !== undefined) term.write(`\r\n[the terminal closed, exit ${event.payload.exit}]\r\n`);
    });
    // Wait until a drag settles before telling the CLI its new size.
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
        params: { agent: agentId, provider, rows: term.rows, cols: term.cols },
      });
      // A reopened terminal shows the output it had on screen.
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
    startTerminal();
  });

  onDestroy(() => {
    observer?.disconnect();
    unlisten?.();
    term?.dispose();
    // The CLI's session is kept by the sidecar, so the next open resumes it.
    invoke("sidecar_call", { method: "terminal_stop", params: { agent: agentId } }).catch(() => {});
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
