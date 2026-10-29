<script lang="ts">
  import BrainGraph from "../graph/BrainGraph.svelte";
  import type { GraphData } from "../graph/model.ts";

  // Loaded by App.svelte through the sidecar bridge; null while loading or after an error.
  let {
    data = null,
    error = null,
    query = "",
    tag = null,
    memory = false,
    selectedId = null,
    viewKey = 0,
    onselect,
    onmemory,
  }: {
    data?: GraphData | null;
    error?: string | null;
    query?: string;
    tag?: string | null;
    memory?: boolean;
    selectedId?: string | null;
    viewKey?: number;
    onselect: (id: string | null) => void;
    onmemory: (on: boolean) => void;
  } = $props();
</script>

<main class="graph" aria-label="Brain graph">
  <header class="tab-header">
    <button
      type="button"
      class="tab"
      aria-pressed={!memory}
      onclick={() => onmemory(false)}>Brain graph</button
    >
    <button
      type="button"
      class="tab"
      aria-pressed={memory}
      onclick={() => onmemory(true)}>Memory</button
    >
  </header>
  <span class="label" aria-hidden="true">GRAPH</span>
  <div class="body">
    {#if data}
      {#key viewKey}
        <BrainGraph {data} {query} {tag} {memory} {selectedId} {onselect} />
      {/key}
    {:else if error}
      <p role="alert">Could not load the vault: {error}</p>
    {:else}
      <p>Loading the vault…</p>
    {/if}
  </div>
</main>

<style>
  .graph {
    grid-area: graph;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    position: relative;
    background: var(--color-bg-0);
    color: var(--color-text-muted);
  }

  /* Dot grid, as in the mockup. Sits over the WebGL canvas, which clears to a solid colour. */
  .graph::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: 1;
    pointer-events: none;
    background-image: radial-gradient(
      color-mix(in srgb, var(--color-accent) 35%, transparent) 1.5px,
      transparent 2px
    );
    background-size: 34px 34px;
  }

  .graph > .tab-header {
    position: relative;
    z-index: 2;
  }

  /* The pane's name in the corner, as in the mockup. */
  .label {
    position: absolute;
    left: var(--space-3);
    top: calc(var(--layout-tab-header-height) + var(--space-2));
    z-index: 2;
    pointer-events: none;
    font-family: "Press Start 2P", monospace;
    font-size: 9px;
    color: var(--color-md-text-muted);
  }

  /* Obsidian's tab header: a strip above the pane, the active tab lifted onto the pane colour. */
  .tab-header {
    display: flex;
    align-items: stretch;
    height: var(--layout-tab-header-height);
    background: var(--color-bg-1);
    border-bottom: 1px solid var(--color-border);
  }

  .tab {
    display: flex;
    align-items: center;
    padding: 0 var(--space-3);
    font: inherit;
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    background: var(--color-bg-1);
    border: 0;
    border-right: 1px solid var(--color-border);
    cursor: pointer;
  }

  .tab[aria-pressed="true"] {
    color: var(--color-text);
    background: var(--color-bg-0);
  }

  .body {
    position: relative;
    flex: 1;
    min-height: 0;
    display: grid;
    place-items: center;
  }

  .body > :global(.brain) {
    place-self: stretch;
  }
</style>
