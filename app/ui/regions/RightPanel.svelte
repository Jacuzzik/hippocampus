<script lang="ts">
  import Assistant from "../assistant/Assistant.svelte";

  // Kept mounted when hidden so the chat session and its tool log survive a toggle.
  let { open = true }: { open?: boolean } = $props();
</script>

<div class="right-panel" hidden={!open}>
  <Assistant />
</div>

<style>
  .right-panel {
    grid-area: panel;
    display: flex;
    min-width: 0;
    min-height: 0;
  }

  .right-panel[hidden] {
    display: none;
  }

  .right-panel > :global(.assistant) {
    flex: 1;
    min-width: 0;
  }
</style>
