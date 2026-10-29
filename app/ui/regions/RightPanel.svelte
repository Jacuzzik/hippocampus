<script lang="ts">
  import Assistant from "../assistant/Assistant.svelte";

  // Kept mounted when hidden so the chat session and its tool log survive a toggle.
  let { open = true }: { open?: boolean } = $props();
</script>

<div class="right-panel" hidden={!open}>
  <div class="column">
    <div class="tabs" role="tablist">
      <span class="tab on" role="tab" aria-selected="true">CLAUDE CODE</span>
      <span class="tab" role="tab" aria-selected="false">PROVIDER</span>
      <span class="tab" role="tab" aria-selected="false">TOOLS</span>
    </div>
    <Assistant />
  </div>
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

  /* The dark terminal box from the mockup: the assistant's chat sits inside it. */
  .column {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    margin: var(--space-2);
    padding: var(--space-2);
    background: var(--color-bg-0);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
  }

  .tabs {
    display: flex;
    gap: var(--space-2);
    padding: var(--space-2);
    border-bottom: 1px solid var(--color-border);
  }

  .tab {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
  }

  .tab.on {
    background: var(--color-accent);
    color: var(--color-accent-on);
    border-color: var(--color-accent);
  }

  /* The mockup has no orb header in the sidebar. Hidden by clipping, not display:none, so the status stays for screen readers. */
  .column :global(.assistant .head) {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .column > :global(.assistant) {
    background: transparent;
    border-left: none;
    padding: var(--space-2);
    flex: 1;
    min-height: 0;
    min-width: 0;
  }
</style>
