<script lang="ts">
  // Shown over the app on startup: a skeleton of the window (the icon rail, the top bar, the agent
  // cards and the board) in shimmering grey blocks, so the layout is there before its content.
  // When the vault and the agent terminals have loaded (the `ready` prop), it fades out at once.
  // A 2-minute safety cap lifts it even if something hangs.
  import { boot } from "../owner/bootTasks.svelte.ts";

  let { ready }: { ready: boolean } = $props();

  const FADE_MS = 250;
  let phase = $state<"loading" | "fading" | "gone">("loading");
  let timedOut = $state(false);

  $effect(() => {
    const limit = setTimeout(() => (timedOut = true), 120000);
    return () => clearTimeout(limit);
  });

  $effect(() => {
    if (phase !== "loading" || !(ready || timedOut)) return;
    phase = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "gone"
      : "fading";
  });

  $effect(() => {
    if (phase !== "fading") return;
    const done = setTimeout(() => (phase = "gone"), FADE_MS);
    return () => clearTimeout(done);
  });

  // The step still running, said in words for screen readers and shown small at the bottom.
  const current = $derived(boot.steps.find((step) => !step.done)?.name ?? "");
</script>

{#if phase !== "gone"}
  <div
    class="loading"
    class:fading={phase === "fading"}
    style="--fade-ms: {FADE_MS}ms"
    role="status"
    aria-live="polite"
    aria-label="Starting Hippocampus"
  >
    <div class="rail" aria-hidden="true">
      {#each [0, 1, 2, 3] as i (i)}
        <span class="skeleton dot"></span>
      {/each}
    </div>
    <div class="side" aria-hidden="true">
      <span class="skeleton line" style:width="60%"></span>
      <span class="skeleton field"></span>
      <span class="skeleton field"></span>
      {#each [70, 50, 62, 44, 56] as w (w)}
        <span class="skeleton line" style:width="{w}%"></span>
      {/each}
    </div>
    <div class="main" aria-hidden="true">
      <div class="bar">
        {#each [0, 1, 2, 3, 4] as i (i)}
          <span class="skeleton pill"></span>
        {/each}
      </div>
      <div class="graph">
        {#each [[30, 20], [55, 45], [40, 70], [70, 30], [22, 60]] as [x, y] (`${x}-${y}`)}
          <span class="skeleton node" style:left="{x}%" style:top="{y}%"></span>
        {/each}
      </div>
    </div>
    <div class="panel" aria-hidden="true">
      <span class="skeleton line" style:width="40%"></span>
      <div class="tabs">
        {#each [...Array(11).keys()] as i (i)}
          <span class="skeleton tab"></span>
        {/each}
      </div>
      <span class="skeleton term"></span>
      <span class="skeleton field tall"></span>
    </div>
    <div class="status" aria-hidden="true">
      {#each [0, 1] as i (i)}
        <div class="card">
          <span class="skeleton avatar"></span>
          <div class="lines">
            <span class="skeleton line" style:width="70%"></span>
            <span class="skeleton line" style:width="50%"></span>
            <span class="skeleton line" style:width="35%"></span>
          </div>
        </div>
      {/each}
    </div>
    {#if current}<p class="step">{current}…</p>{/if}
  </div>
{/if}

<style>
  .loading {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: grid;
    grid-template-columns:
      var(--layout-ribbon-width) var(--layout-sidebar-width)
      minmax(0, 1fr) 500px;
    grid-template-rows: minmax(0, 1fr) 136px;
    grid-template-areas:
      "rail side main panel"
      "status status status status";
    overflow: hidden;
    background: var(--color-bg-0);
    opacity: 1;
    transition: opacity var(--fade-ms) ease;
  }

  .loading.fading {
    opacity: 0;
  }

  .skeleton {
    flex: none;
  }

  .rail,
  .side,
  .panel,
  .status {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--color-bg-1);
  }

  .rail {
    grid-area: rail;
    align-items: center;
    padding-inline: 0;
    border-right: 1px solid var(--color-border);
  }

  .dot {
    width: var(--size-24);
    height: var(--size-24);
    border-radius: var(--radius-sm);
  }

  .side {
    grid-area: side;
    border-right: 1px solid var(--color-border);
  }

  .field {
    height: var(--size-28);
  }

  .field.tall {
    height: 64px;
  }

  .main {
    grid-area: main;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .bar {
    display: flex;
    gap: var(--space-2);
    padding: var(--space-2);
  }

  .pill {
    width: 72px;
    height: var(--size-28);
  }

  .graph {
    position: relative;
    flex: 1 1 auto;
  }

  .node {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 50%;
  }

  .panel {
    grid-area: panel;
    min-height: 0;
    border-left: 1px solid var(--color-border);
  }

  .tabs {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-1);
  }

  .tab {
    height: var(--size-28);
  }

  .term {
    flex: 1 1 auto;
    height: auto;
  }

  .status {
    grid-area: status;
    flex-direction: row;
    align-items: center;
    border-top: 1px solid var(--color-border);
  }

  .card {
    display: flex;
    gap: var(--space-3);
    width: 320px;
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .lines {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    gap: var(--space-2);
  }

  .avatar {
    width: 56px;
    height: 56px;
    border-radius: var(--radius-sm);
  }

  .step {
    position: absolute;
    right: var(--space-3);
    bottom: var(--space-3);
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  /* Narrow windows: the side columns go, as they do in the app. */
  @media (max-width: 900px) {
    .loading {
      grid-template-columns: var(--layout-ribbon-width) minmax(0, 1fr);
      grid-template-areas:
        "rail main"
        "status status";
    }

    .side,
    .panel {
      display: none;
    }
  }
</style>
