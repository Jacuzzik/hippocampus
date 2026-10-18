<script lang="ts">
  import GraphPlaceholder from "./regions/GraphPlaceholder.svelte";
  import LeftRail from "./regions/LeftRail.svelte";
  import RightPanel from "./regions/RightPanel.svelte";
  import TopBar from "./regions/TopBar.svelte";
</script>

<div class="shell">
  <TopBar />
  <LeftRail />
  <GraphPlaceholder />
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
