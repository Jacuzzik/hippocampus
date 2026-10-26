<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import GraphRegion from "./regions/GraphRegion.svelte";
  import NoteSidebar from "./regions/NoteSidebar.svelte";
  import Ribbon from "./regions/Ribbon.svelte";
  import RightPanel from "./regions/RightPanel.svelte";
  import StatusBar from "./regions/StatusBar.svelte";
  import CommandBox, { type Item } from "./overlays/CommandBox.svelte";
  import type { GraphData } from "./graph/model.ts";

  let data = $state<GraphData | null>(null);
  let error = $state<string | null>(null);
  let query = $state("");
  let tag = $state<string | null>(null);
  let selectedId = $state<string | null>(null);
  let sidebarOpen = $state(true);
  let panelOpen = $state(true);
  // Which overlay box is open: the quick switcher (Ctrl+O) or the command palette (Ctrl+P).
  let box = $state<"switcher" | "palette" | null>(null);

  // Ctrl on Linux and Windows, Cmd on macOS. Both shortcuts take over the browser default.
  function onKey(e: KeyboardEvent): void {
    if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
    if (e.key === "o") box = "switcher";
    else return;
    e.preventDefault();
  }

  const noteItems = $derived<Item[]>(
    (data?.nodes ?? []).map((node) => ({
      id: node.id,
      label: node.title,
      hint: node.id,
      run: () => (selectedId = node.id),
    })),
  );

  onMount(async () => {
    try {
      data = await invoke<GraphData>("sidecar_call", { method: "graph" });
    } catch (cause) {
      error = String(cause);
    }
  });
</script>

<svelte:window onkeydown={onKey} />

{#if box === "switcher"}
  <CommandBox
    items={noteItems}
    placeholder="Open a note by name"
    label="Quick switcher"
    onclose={() => (box = null)}
  />
{/if}

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
