<script lang="ts">
  import Assistant from "../assistant/Assistant.svelte";
  import AgentStatus from "../owner/AgentStatus.svelte";
  import OwnerPanel from "../owner/OwnerPanel.svelte";

  // Kept mounted when hidden so the chat session and its tool log survive a toggle.
  let { open = true }: { open?: boolean } = $props();
</script>

<div class="right-panel" hidden={!open}>
  <div class="column">
    <AgentStatus />
    <Assistant />
  </div>
  <OwnerPanel />
</div>

<style>
  .right-panel {
    grid-area: panel;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }

  .right-panel[hidden] {
    display: none;
  }

  .column {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }

  .column > :global(.assistant) {
    flex: 1;
    min-height: 0;
    min-width: 0;
  }
</style>
