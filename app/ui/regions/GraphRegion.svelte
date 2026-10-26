<script lang="ts">
  import BrainGraph from "../graph/BrainGraph.svelte";
  import type { GraphData } from "../graph/model.ts";

  // Loaded by App.svelte through the sidecar bridge; null while loading or after an error.
  let {
    data = null,
    error = null,
    query = "",
    tag = null,
    selectedId = null,
    onselect,
  }: {
    data?: GraphData | null;
    error?: string | null;
    query?: string;
    tag?: string | null;
    selectedId?: string | null;
    onselect: (id: string | null) => void;
  } = $props();
</script>

<main class="graph" aria-label="Brain graph">
  <header class="tab-header">
    <span class="tab" aria-current="page">Brain graph</span>
  </header>
  <div class="body">
    {#if data}
      <BrainGraph {data} {query} {tag} {selectedId} {onselect} />
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
    background: var(--color-bg-0);
    color: var(--color-text-muted);
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
    font-size: var(--font-size-sm);
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
