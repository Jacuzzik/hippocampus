<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import GraphRegion from "./regions/GraphRegion.svelte";
  import LeftRail from "./regions/LeftRail.svelte";
  import RightPanel from "./regions/RightPanel.svelte";
  import TopBar from "./regions/TopBar.svelte";
  import type { GraphData } from "./graph/model.ts";

  let data = $state<GraphData | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      data = await invoke<GraphData>("sidecar_call", { method: "graph" });
    } catch (cause) {
      error = String(cause);
    }
  });
</script>

<div class="shell">
  <TopBar />
  <LeftRail />
  <GraphRegion {data} {error} />
  <RightPanel />
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns:
      var(--layout-left-rail-width) minmax(0, 1fr)
      var(--layout-right-panel-width);
    grid-template-rows: var(--layout-topbar-height) minmax(0, 1fr);
    grid-template-areas:
      "top top top"
      "rail graph panel";
    height: 100%;
  }
</style>
