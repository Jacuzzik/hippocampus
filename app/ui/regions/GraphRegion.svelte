<script lang="ts">
  import BrainGraph from "../graph/BrainGraph.svelte";
  import type { GraphData } from "../graph/model.ts";

  // The app does not load a vault yet: the sidecar is not started from the shell (see the D3 handoff).
  let { data = null }: { data?: GraphData | null } = $props();
</script>

<main class="graph" aria-label="Brain graph">
  {#if data}
    <BrainGraph {data} />
  {:else}
    <p>No vault is open. Opening a vault arrives with the sidecar bridge.</p>
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
