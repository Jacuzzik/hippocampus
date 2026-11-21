<script lang="ts">
  // Shows how long a job has been running, with a button to stop waiting for it.
  // Stopping only stops the window waiting: the job itself is not cancelled.
  import { onDestroy, onMount } from "svelte";

  let { label, onstop }: { label: string; onstop: () => void } = $props();
  const started = Date.now();
  let seconds = $state(0);
  let timer: ReturnType<typeof setInterval> | undefined;
  onMount(() => {
    timer = setInterval(
      () => (seconds = Math.floor((Date.now() - started) / 1000)),
      1000,
    );
  });
  onDestroy(() => clearInterval(timer));
</script>

<p class="wait" role="status">
  {label}… {seconds} s
  <button type="button" class="stop" onclick={onstop}>Stop waiting</button>
</p>

<style>
  .wait {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: var(--space-2) 0 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }
  .stop {
    font: inherit;
    color: inherit;
    background: none;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }
</style>
