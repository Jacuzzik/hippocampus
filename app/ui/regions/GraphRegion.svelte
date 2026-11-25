<script lang="ts">
  import Loading from "../controls/Loading.svelte";
  import { every } from "../poll.ts";
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import type { GraphData } from "../graph/model.ts";
  import { prefs } from "../prefs.svelte.ts";

  type System = {
    cpu: number;
    ram: number;
    swap: number;
    disk: number;
    disk_free: number;
  };
  let system = $state<System | null>(null);

  // Read only, so a failed read just leaves the last value on screen.
  onMount(() => {
    const read = () =>
      invoke<System>("sidecar_call", { method: "system" }).then(
        (value) => (system = value),
        (cause) => console.error("Could not read system stats", cause),
      );
    void read();
    return every(read, 3000);
  });

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
    ondashboards,
    onadd,
    onpalette,
    onlock,
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
    ondashboards: () => void;
    onadd: () => void;
    onpalette: () => void;
    /** Opens the setting that locks and unlocks the dashboards. */
    onlock: () => void;
  } = $props();
</script>

<main class="graph" aria-label="Brain graph">
  <header class="topbar">
    <div class="stats" aria-label="System load">
      <span title="Total CPU use"
        >CPU <b>{system ? `${system.cpu}%` : "…"}</b></span
      >
      <span title="RAM in use"
        >RAM <b>{system ? `${system.ram}%` : "…"}</b></span
      >
      <span title="Swap in use: disk used as RAM overflow; high means slow"
        >SWAP <b>{system ? `${system.swap}%` : "…"}</b></span
      >
      <span title="Disk in use"
        >DISK <b>{system ? `${system.disk}%` : "…"}</b></span
      >
      <span title="Free space on the drive that holds the app data"
        >FREE <b class="wide">{system ? `${system.disk_free} GB` : "…"}</b
        ></span
      >
    </div>
    <div class="icons">
      <button
        type="button"
        aria-label="Dashboards"
        title="Dashboards · Ctrl+D"
        onclick={ondashboards}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="3" width="8" height="10" rx="1" />
          <rect x="13" y="3" width="8" height="6" rx="1" />
          <rect x="13" y="11" width="8" height="10" rx="1" />
          <rect x="3" y="15" width="8" height="6" rx="1" />
        </svg>
      </button>
      <button
        type="button"
        aria-label={prefs.dashboardsLocked
          ? "Dashboards are locked"
          : "Dashboards are unlocked"}
        title={prefs.dashboardsLocked
          ? "Dashboards are locked"
          : "Dashboards are unlocked"}
        onclick={onlock}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="5" y="11" width="14" height="10" rx="2" />
          {#if prefs.dashboardsLocked}
            <path d="M8 11V7a4 4 0 0 1 8 0v4" />
          {:else}
            <path d="M8 11V7a4 4 0 0 1 7.5-2" />
          {/if}
        </svg>
      </button>
      <button
        type="button"
        aria-label="Add an agent"
        title="Add an agent"
        onclick={onadd}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10" cy="8" r="4" />
          <path d="M3 21c0-4 3-7 7-7 1.5 0 2.9.4 4 1.1M19 14v6M16 17h6" />
        </svg>
      </button>
      <button
        type="button"
        aria-label="Command palette"
        title="Command palette · Ctrl+P"
        onclick={onpalette}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="M16.5 16.5 21 21" />
        </svg>
      </button>
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
    </div>
  </header>
  {#if !fullscreen}
    <div class="body">
      {#if data}
        {#key viewKey}
          <!-- B.05: the graph code loads when the first graph is shown, not at start-up. -->
          {#await import("../graph/BrainGraph.svelte")}
            <Loading what="the graph" />
          {:then { default: BrainGraph }}
            <BrainGraph {data} {query} {tag} {memory} {selectedId} {onselect} />
          {:catch cause}
            <p role="alert">Could not load the graph: {String(cause)}</p>
          {/await}
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

  .graph > .topbar {
    position: relative;
    z-index: 2;
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

  .stats {
    display: flex;
    margin-inline-end: auto;
    align-items: center;
    gap: var(--space-3);
    padding: 0 var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  /* Each value keeps one width, so the row does not shift as the numbers change. */
  .stats b {
    display: inline-block;
    min-width: 6ch;
    font-weight: normal;
    font-variant-numeric: tabular-nums;
    color: var(--color-text);
  }

  .stats b.wide {
    min-width: 9ch;
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
    width: var(--size-28);
    height: var(--size-28);
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
    width: var(--size-16);
    height: var(--size-16);
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
