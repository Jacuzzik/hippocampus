<!-- The one terminal in the app: an agent's own CLI in a pseudo-terminal, drawn by xterm.js.
     The main agent and every added agent use it; the props below hold the few ways they differ. -->
<script lang="ts" module>
  export type TerminalState = "running" | "exited" | "stopped" | "failed";
</script>

<script lang="ts">
  import { cssToken, fontToken } from "../cssToken.ts";
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onDestroy, onMount } from "svelte";
  import { bootTask } from "../owner/bootTasks.svelte.ts";
  import { backend } from "../backend.svelte.ts";
  import { Terminal } from "@xterm/xterm";
  import { FitAddon } from "@xterm/addon-fit";
  import "@xterm/xterm/css/xterm.css";

  let {
    agentId,
    provider,
    model,
    folder,
    blockTools = false,
    fontSize = 12,
    label = "Live terminal",
    hidden = false,
    restore = "replay",
    trimRow = false,
    followEngine = false,
    onoutput,
    onstate,
  }: {
    agentId: string;
    provider: string;
    model?: string;
    folder?: string;
    /** On, the CLI runs without shell, file writes or web. Call restart() after changing it. */
    blockTools?: boolean;
    fontSize?: number;
    label?: string;
    hidden?: boolean;
    /** How a reopened terminal gets its screen back: "replay" writes the saved output; "redraw" clears
        the screen at the first real size and makes the CLI draw again (for a terminal mounted hidden). */
    restore?: "replay" | "redraw";
    /** Gives the bottom row back, so the last line sits inside the box and not on its edge. */
    trimRow?: boolean;
    /** The main agent only: a model change in the Monitor tab starts a new session in this terminal. */
    followEngine?: boolean;
    onoutput?: (data: string) => void;
    onstate?: (state: TerminalState, exitCode: number | null) => void;
  } = $props();

  let screen: HTMLDivElement;
  let term: Terminal | null = null;
  let fit: FitAddon | null = null;
  let unlisten: (() => void) | null = null;
  let observer: ResizeObserver | null = null;
  let settle: ReturnType<typeof setTimeout> | undefined;
  let restarting = false;
  let onEngineChanged: ((e: Event) => void) | null = null;
  // "redraw" only. False until the terminal has been fitted to a visible box: a panel mounted hidden starts
  // its CLI at a default width, so the first output is laid out for that width and not for the real box.
  let sized = false;

  function resizeCli(rows: number, cols: number): Promise<unknown> {
    return invoke("sidecar_call", {
      method: "terminal_resize",
      params: { agent: agentId, rows, cols },
    }).catch(() => {});
  }

  function sendSize(): void {
    if (!term || !fit || !screen) return;
    // A hidden or mid-animation panel reports a tiny width; telling the CLI that makes it redraw one or two characters per line.
    if (screen.clientWidth < 200 || screen.clientHeight < 80) return;
    try {
      fit.fit();
    } catch {
      // The terminal was closed or has not drawn yet; the next size change tries again.
      return;
    }
    if (trimRow && term.rows > 1) term.resize(term.cols, term.rows - 1);
    const { rows, cols } = term;
    if (restore !== "redraw" || sized) {
      void resizeCli(rows, cols);
      return;
    }
    // First real size: what is on screen was drawn for the wrong width, and re-wrapping it leaves the CLI's
    // cursor moves pointing at the wrong rows (overlapping and missing letters). Start from a blank screen
    // and make the CLI draw everything again: one row off and back, the same nudge a reattach uses.
    sized = true;
    term.reset();
    void resizeCli(rows + 1, cols).then(() => resizeCli(rows, cols));
  }

  async function startTerminal(): Promise<void> {
    // Colours are read from the app's dark tokens, so the terminal matches the panels.
    const bg = cssToken("md-bg-0");
    const fg = cssToken("md-text");
    term = new Terminal({
      // The app's monospace token, with the Nerd Font variant first for the icons some CLIs draw.
      fontFamily: `"JetBrainsMono Nerd Font Mono", ${fontToken("mono")}`,
      fontSize,
      cursorBlink: true,
      convertEol: true,
      theme: { background: bg, foreground: fg, cursor: fg },
    });
    fit = new FitAddon();
    term.loadAddon(fit);
    term.open(screen);
    // xterm measures a cell once at open; nudge it after the font loads so cells match the drawn glyphs.
    const opened = term;
    document.fonts?.ready.then(() => {
      if (term !== opened) return;
      const size = opened.options.fontSize ?? 12;
      opened.options.fontSize = size + 0.01;
      opened.options.fontSize = size;
      sendSize();
    });
    term.onData((data) => {
      // Focus in/out reports are not typing; sent to the CLI they show as ^[[O text on screen.
      if (data === "\x1b[I" || data === "\x1b[O") return;
      invoke("sidecar_call", {
        method: "terminal_input",
        params: { agent: agentId, data },
      }).catch((cause) =>
        console.error("Could not send to the terminal", cause),
      );
    });
    unlisten = await listen<{
      event?: string;
      agent?: string;
      data?: string;
      exit?: number;
      stopped?: boolean;
    }>("sidecar-event", (event) => {
      if (
        event.payload.event !== "terminal" ||
        event.payload.agent !== agentId ||
        !term
      )
        return;
      if (event.payload.data !== undefined) {
        term.write(event.payload.data);
        onoutput?.(event.payload.data);
      }
      // A model change stops the old process on purpose; the new session replaces it, so no "closed" line.
      if (event.payload.exit !== undefined && !restarting) {
        term.write(
          event.payload.stopped
            ? "\r\n[the terminal was stopped]\r\n"
            : `\r\n[the terminal closed, exit ${event.payload.exit}]\r\n`,
        );
        onstate?.(
          event.payload.stopped ? "stopped" : "exited",
          event.payload.exit,
        );
      }
    });
    if (followEngine) {
      onEngineChanged = (e: Event) => {
        const detail = (e as CustomEvent<{ provider?: string; model?: string }>)
          .detail;
        restarting = true;
        term?.reset();
        // After the new CLI starts, resend the size so it redraws at the right dimensions (fixes garbled output).
        startSession(detail?.provider ?? provider)
          .then(() => setTimeout(sendSize, 300))
          .finally(() => setTimeout(() => (restarting = false), 1500));
      };
      window.addEventListener("engine-changed", onEngineChanged);
    }
    // Wait until a drag settles before telling the CLI its new size, so it is not sent on every frame.
    observer = new ResizeObserver(() => {
      clearTimeout(settle);
      settle = setTimeout(sendSize, 200);
    });
    observer.observe(screen);
    fit.fit();
    await startSession(provider);
  }

  // Starts the CLI, or reattaches to the one already running for this agent.
  async function startSession(p: string): Promise<void> {
    if (!term) return;
    try {
      const started = await invoke<{ replay?: string }>("sidecar_call", {
        method: "terminal_start",
        params: {
          agent: agentId,
          provider: p,
          model,
          folder,
          rows: term.rows,
          cols: term.cols,
          block_tools: blockTools,
        },
      });
      // reset() clears modes left by the old screen (alt buffer, cursor, colours) so the replay draws cleanly.
      if (restore === "replay" && started?.replay) {
        term.reset();
        term.write(started.replay);
      }
      onstate?.("running", null);
    } catch (cause) {
      onstate?.("failed", null);
      term?.write(`${String(cause)}\r\n`);
    }
  }

  // Drops the screen and its listeners. The CLI is left running: stopping it here sent SIGTERM on every
  // reload (exit 143). The next open reattaches to it.
  function close(): void {
    clearTimeout(settle);
    observer?.disconnect();
    unlisten?.();
    if (onEngineChanged)
      window.removeEventListener("engine-changed", onEngineChanged);
    term?.dispose();
    observer = null;
    unlisten = null;
    onEngineChanged = null;
    term = null;
    fit = null;
  }

  /** A new session on a fresh screen, for a setting the CLI reads only at start. Stop the old CLI first. */
  export async function restart(): Promise<void> {
    close();
    await startTerminal();
  }

  // The − and + buttons change the text size; the terminal redraws and tells the CLI its new size.
  $effect(() => {
    const size = fontSize; // read before the early return, so the effect tracks it from the start
    if (!term) return;
    term.options.fontSize = size;
    sendSize();
  });

  // The agent's program stops when the backend does. When the backend comes back, start it again
  // (it resumes its last session) instead of leaving a dead screen that looks alive.
  let restartsSeen = backend.restarts;
  $effect(() => {
    const count = backend.restarts;
    if (count === restartsSeen) return;
    restartsSeen = count;
    void restart().then(() =>
      term?.write(
        "\r\n[the backend restarted; this agent was started again]\r\n",
      ),
    );
  });

  onMount(() => {
    // Counted as start-up work so the loading screen waits for this terminal.
    const done = bootTask();
    startTerminal().finally(done);
  });

  onDestroy(close);
</script>

<div class="screen" bind:this={screen} aria-label={label} {hidden}></div>

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
