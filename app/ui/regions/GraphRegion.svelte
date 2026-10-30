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
    fullscreen = false,
    onselect,
    onfullscreen,
  }: {
    data?: GraphData | null;
    error?: string | null;
    query?: string;
    tag?: string | null;
    memory?: boolean;
    selectedId?: string | null;
    viewKey?: number;
    fullscreen?: boolean;
    onselect: (id: string | null) => void;
    onfullscreen: () => void;
  } = $props();
</script>

<main class="graph" aria-label="Brain graph">
  <header class="topbar">
    <div class="icons">
      <button
        type="button"
        aria-label="Full screen layout"
        aria-pressed={fullscreen}
        title="Full screen layout"
        onclick={onfullscreen}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
        </svg>
      </button>
      <!-- Dummy placeholders: not wired yet. -->
      <button type="button" aria-label="Dark or light theme" title="Theme (not wired yet)">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="8" />
          <path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" />
        </svg>
      </button>
      <button type="button" aria-label="Personal board" title="Personal board (not wired yet)">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="4" y="4" width="7" height="7" rx="1" />
          <rect x="13" y="4" width="7" height="7" rx="1" />
          <rect x="4" y="13" width="7" height="7" rx="1" />
          <rect x="13" y="13" width="7" height="7" rx="1" />
        </svg>
      </button>
    </div>
  </header>
  {#if !fullscreen}
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
  {/if}
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

  .graph > .topbar {
    position: relative;
    z-index: 2;
  }

  /* The pane's name in the bottom-left corner: the top corner holds the graph controls. */
  .label {
    position: absolute;
    left: var(--space-3);
    bottom: var(--space-2);
    z-index: 2;
    pointer-events: none;
    font-family: "Press Start 2P", monospace;
    font-size: 9px;
    color: var(--color-md-text-muted);
  }

  /* The top bar: a strip above the pane, with the icon buttons on the right. */
  .topbar {
    display: flex;
    justify-content: flex-end;
    align-items: stretch;
    height: var(--layout-tab-header-height);
    background: var(--color-bg-1);
    border-bottom: 1px solid var(--color-border);
  }

  .icons {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0 var(--space-2);
  }

  .icons button {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    padding: 0;
    color: var(--color-text-muted);
    background: none;
    border: 0;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .icons button:hover,
  .icons button[aria-pressed="true"] {
    color: var(--color-text);
    background: var(--color-surface);
  }

  .icons svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
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
