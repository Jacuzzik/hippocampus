<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import GraphRegion from "./regions/GraphRegion.svelte";
  import NoteSidebar from "./regions/NoteSidebar.svelte";
  import Ribbon from "./regions/Ribbon.svelte";
  import RightPanel from "./regions/RightPanel.svelte";
  import StatusBar from "./regions/StatusBar.svelte";
  import type { GraphData } from "./graph/model.ts";

  let data = $state<GraphData | null>(null);
  let error = $state<string | null>(null);
  let query = $state("");
  let tag = $state<string | null>(null);
  let selectedId = $state<string | null>(null);
  let sidebarOpen = $state(true);
  let panelOpen = $state(true);

  onMount(async () => {
    try {
      data = await invoke<GraphData>("sidecar_call", { method: "graph" });
    } catch (cause) {
      error = String(cause);
    }
  });
</script>

<div class="shell" class:no-sidebar={!sidebarOpen} class:no-panel={!panelOpen}>
  <Ribbon bind:sidebarOpen bind:panelOpen />
  {#if sidebarOpen && data}
    <NoteSidebar {data} bind:query bind:tag bind:selectedId />
  {/if}
  <GraphRegion
    {data}
    {error}
    {query}
    {tag}
    {selectedId}
    onselect={(id) => (selectedId = id)}
  />
  <RightPanel open={panelOpen} />
  <StatusBar {data} />
</div>

<style>
  .shell {
    --sidebar-col: var(--layout-sidebar-width);
    --panel-col: var(--layout-right-panel-width);
    display: grid;
    grid-template-columns:
      var(--layout-ribbon-width) var(--sidebar-col) minmax(0, 1fr)
      var(--panel-col);
    grid-template-rows: minmax(0, 1fr) var(--layout-status-bar-height);
    grid-template-areas:
      "rail sidebar graph panel"
      "status status status status";
    height: 100%;
    overflow: hidden;
  }

  /* Narrow windows (960px wide) keep the graph readable: the panels yield width first. */
  @media (max-width: 1100px) {
    .shell {
      --sidebar-col: 200px;
      --panel-col: min(var(--layout-right-panel-width), 34vw);
    }
  }

  .shell.no-sidebar {
    --sidebar-col: 0px;
  }

  .shell.no-panel {
    --panel-col: 0px;
  }
</style>
