// Messages typed in a message box go into an agent's terminal. While the CLI is working,
// messages wait in a queue and are sent one by one when it is done.
// When an agent's context is 70% full and it is idle, the app queues a compact prompt. It also
// tells the agent to read its priority notes, so the notes survive the compact.
import { invoke } from "@tauri-apps/api/core";

// Claude Code prints this line only while it is working; it can pause without other output.
const WORKING_MARK = "esc to interrupt";
const BUSY_MS = 3000;
const COMPACT_AT_PERCENT = 70;
// The sidecar reads the context size; the tick runs every second, so this checks about every 30 seconds.
const CHECK_EVERY_TICKS = 30;

function compactPrompt(agentId: string): string {
  return `/compact Keep the current task, recent decisions, open questions, and file paths in play. Drop resolved tangents. Read ${agentId}-PriorityNotes.`;
}

// agentId is read each time it is used, so the queue follows the agent the panel shows now.
export function createTerminalQueue(agentId: () => string) {
  let busyUntil = 0;
  let ticks = 0;
  let percent = 0;
  let items = $state<string[]>([]);

  function flush(): void {
    if (items.length === 0 || Date.now() < busyUntil) return;
    const [next, ...rest] = items;
    items = rest;
    busyUntil = Date.now() + BUSY_MS;
    invoke("sidecar_call", { method: "terminal_input", params: { agent: agentId(), data: `${next}\r` } }).catch((cause) =>
      console.error("Could not send to the terminal", cause),
    );
  }

  function checkContext(): void {
    invoke<{ percent: number }>("sidecar_call", { method: "terminal_context", params: { agent: agentId() } })
      .then((result) => (percent = result.percent))
      .catch((cause) => console.error("Could not read the context size", cause));
  }

  return {
    /** The messages still waiting, oldest first. */
    get items() {
      return items;
    },
    /** Call with each chunk the terminal prints. */
    output(data: string): void {
      if (data.includes(WORKING_MARK)) busyUntil = Date.now() + BUSY_MS;
    },
    /** Queue a message and send it now if the CLI is idle. */
    send(text: string): void {
      items = [...items, text];
      flush();
    },
    /** Call on a timer: queues a compact when the context is 70% full and the CLI is idle, then sends the queue. */
    tick(): void {
      if (ticks++ % CHECK_EVERY_TICKS === 0) checkContext();
      if (items.length === 0 && percent >= COMPACT_AT_PERCENT && Date.now() >= busyUntil) {
        // Reset until the next check, so the same full context is not compacted twice.
        percent = 0;
        items = [compactPrompt(agentId())];
      }
      flush();
    },
  };
}
