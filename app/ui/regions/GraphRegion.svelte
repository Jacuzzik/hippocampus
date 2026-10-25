<script lang="ts">
  import BrainGraph from "../graph/BrainGraph.svelte";
  import type { GraphData } from "../graph/model.ts";

  // Loaded by App.svelte through the sidecar bridge; null while loading or after an error.
  let {
    data = null,
    error = null,
  }: { data?: GraphData | null; error?: string | null } = $props();
</script>

<main class="graph" aria-label="Brain graph">
  {#if data}
    <BrainGraph {data} />
  {:else if error}
    <p role="alert">Could not load the vault: {error}</p>
  {:else}
    <p>Loading the vault…</p>
  {/if}
</main>

<style>
  .graph {
    grid-area: graph;
    position: relative;
    display: grid;
    place-items: center;
    min-height: 0;
    background: var(--color-bg-0);
    color: var(--color-text-muted);
  }

  .graph > :global(.brain) {
    place-self: stretch;
  }
</style>
