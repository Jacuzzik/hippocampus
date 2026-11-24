<script lang="ts">
  // 7.27: Ctrl+Shift+D starts listening; pressing it again stops, turns the speech into text with a program on
  // this computer, and types it where the cursor is (or copies it). The recording is deleted as soon as it is read.
  import { listen } from "@tauri-apps/api/event";
  import { onMount } from "svelte";
  import { call } from "../settings/call";

  let phase = $state<"idle" | "listening" | "working">("idle");
  let message = $state("");
  let timer: ReturnType<typeof setTimeout> | undefined;

  function say(text: string): void {
    message = text;
    clearTimeout(timer);
    timer = setTimeout(() => (message = ""), 6000);
  }
  async function toggle(): Promise<void> {
    if (phase === "working") return;
    try {
      if (phase === "idle") {
        await call("dictation_start");
        phase = "listening";
        message = "";
      } else {
        phase = "working";
        const done = await call<{ text: string; did: string }>(
          "dictation_stop",
        );
        say(done.text ? `${done.did}: ${done.text}` : done.did);
        phase = "idle";
      }
    } catch (cause) {
      phase = "idle";
      say(String(cause));
    }
  }
  onMount(() => {
    let stop: (() => void) | undefined;
    listen("dictation-toggle", () => void toggle())
      .then((un) => (stop = un))
      .catch(() => {});
    const onKey = (e: KeyboardEvent): void => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.code === "KeyD") {
        e.preventDefault();
        void toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      stop?.();
      window.removeEventListener("keydown", onKey);
    };
  });
</script>

{#if phase !== "idle" || message}
  <div class="bubble" role="status" aria-live="polite">
    {#if phase === "listening"}Listening. Press Ctrl+Shift+D to finish.
    {:else if phase === "working"}Turning your speech into text…
    {:else}{message}{/if}
  </div>
{/if}

<style>
  .bubble {
    position: fixed;
    right: var(--space-3);
    bottom: var(--space-3);
    max-width: 360px;
    padding: var(--space-2) var(--space-3);
    background: var(--color-bg-1);
    border: 1px solid var(--color-accent);
    border-radius: var(--radius-md);
    z-index: 30;
    font-size: var(--font-size-sm);
  }
</style>
