<script lang="ts">
  // Session replay (N.11): steps through an agent's tool calls in the order they ran, one at a time,
  // with the time each took to follow the one before. Made from the same session file Traces reads.
  import { onDestroy } from "svelte";

  type Trace = {
    at: string | null;
    tool: string;
    detail: string;
    status: string;
  };
  let { traces, name }: { traces: Trace[]; name: string } = $props();

  // Traces come newest first; the replay runs oldest first.
  const steps = $derived([...traces].reverse());
  let index = $state(0);
  let playing = $state(false);
  let timer = 0;

  const step = $derived(steps[Math.min(index, steps.length - 1)]);
  const gap = $derived.by(() => {
    const now = step?.at ? Date.parse(step.at) : NaN;
    const before = steps[index - 1]?.at;
    const then = before ? Date.parse(before) : NaN;
    if (Number.isNaN(now) || Number.isNaN(then)) return null;
    const s = Math.max(0, Math.round((now - then) / 1000));
    return s < 60
      ? `${s} s after the one before`
      : `${Math.round(s / 60)} min after the one before`;
  });

  function stop(): void {
    playing = false;
    clearInterval(timer);
  }
  function play(): void {
    if (playing) {
      stop();
      return;
    }
    if (index >= steps.length - 1) index = 0;
    playing = true;
    timer = window.setInterval(() => {
      if (index >= steps.length - 1) stop();
      else index += 1;
    }, 900);
  }
  onDestroy(stop);
</script>

<section class="replay" aria-label="Replay of {name}'s session">
  <div class="bar">
    <button type="button" onclick={play}>{playing ? "Pause" : "Play"}</button>
    <button
      type="button"
      aria-label="Step back"
      disabled={index === 0}
      onclick={() => {
        stop();
        index -= 1;
      }}>‹</button
    >
    <input
      type="range"
      min="0"
      max={Math.max(0, steps.length - 1)}
      aria-label="Replay position"
      bind:value={index}
      oninput={stop}
    />
    <button
      type="button"
      aria-label="Step forward"
      disabled={index >= steps.length - 1}
      onclick={() => {
        stop();
        index += 1;
      }}>›</button
    >
    <output aria-label="Replay step">{index + 1} of {steps.length}</output>
  </div>
  {#if step}
    <div class="step" aria-live="polite">
      <p>
        <span class="tag" class:bad={step.status === "failed"}
          >{step.status}</span
        >
        <strong>{step.tool.replace("mcp__vault__", "")}</strong>
        <small>{(step.at ?? "").replace("T", " ").slice(0, 19)}</small>
        {#if gap}<small>{gap}</small>{/if}
      </p>
      <pre aria-label="What it ran">{step.detail || "(no input recorded)"}</pre>
    </div>
  {/if}
</section>

<style>
  .replay {
    display: grid;
    gap: var(--space-2);
    padding: var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
  }
  .bar {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }
  .bar input {
    flex: 1 1 auto;
    min-width: 0;
  }
  .step p {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
    margin: 0;
  }
  .tag {
    color: var(--color-md-accent);
  }
  .tag.bad {
    color: var(--color-danger);
  }
  small {
    color: var(--color-md-text-muted);
  }
  pre {
    max-height: 10rem;
    margin: var(--space-1) 0 0;
    overflow: auto;
    white-space: pre-wrap;
    font-family: var(--font-mono);
  }
</style>
