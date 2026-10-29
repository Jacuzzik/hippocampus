<script lang="ts">
  import Assistant from "../assistant/Assistant.svelte";
  import TasksPanel from "./TasksPanel.svelte";
  import InboxPanel from "./InboxPanel.svelte";
  import MemoryPanel from "./MemoryPanel.svelte";

  // Kept mounted when hidden so the chat session and its tool log survive a toggle.
  let { open = true }: { open?: boolean } = $props();

  // Only the terminal is built; the rest of the grid is shown and stays disabled.
  // Names match Munder Difflin's Command Center tabs.
  const TABS = [
    "terminal", "monitor", "tasks", "inbox", "ask me", "triggers",
    "history", "memory", "graph", "activity", "skills", "temps",
  ];
  // Tabs that have content so far; the rest stay disabled.
  const LIVE = ["terminal", "tasks", "inbox", "memory"];
  let tab = $state("terminal");
  let fontSize = $state(12);
</script>

<div class="right-panel" hidden={!open}>
  <div class="column" style="--term-size: {fontSize}px">
    <div class="tabs" role="tablist" aria-label="Panels">
      {#each TABS as name (name)}
        <button
          type="button"
          class="tab"
          role="tab"
          aria-selected={tab === name}
          class:on={tab === name}
          disabled={!LIVE.includes(name)}
          title={LIVE.includes(name) ? undefined : "Not built yet"}
          onclick={() => (tab = name)}>{name}</button
        >
      {/each}
    </div>
    <div class="live">
      <span class="dot" aria-hidden="true"></span>
      <span>live · pty hippo</span>
      <span class="size">
        <button type="button" aria-label="Smaller text" onclick={() => (fontSize = Math.max(9, fontSize - 1))}>−</button>
        <output>{fontSize}px</output>
        <button type="button" aria-label="Larger text" onclick={() => (fontSize = Math.min(18, fontSize + 1))}>+</button>
      </span>
    </div>
    <div class="pane" hidden={tab !== "terminal"}>
      <Assistant />
    </div>
    {#if tab === "tasks"}
      <TasksPanel />
    {:else if tab === "inbox"}
      <InboxPanel />
    {:else if tab === "memory"}
      <MemoryPanel />
    {/if}
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
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
    gap: var(--space-1);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--color-border);
  }

  .tab {
    min-height: 44px;
    font-family: "Press Start 2P", monospace;
    font-size: 7px;
    text-transform: uppercase;
    padding: var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text-muted);
    cursor: pointer;
  }

  .tab:disabled {
    cursor: default;
    opacity: 0.6;
  }

  .tab.on {
    background: var(--color-md-accent);
    color: var(--color-md-accent-on);
    border-color: var(--color-md-accent);
  }

  .live {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) 0;
    font-size: var(--font-size-xs);
    color: var(--color-md-text-muted);
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-md-accent);
  }

  .size {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .size button {
    min-width: 44px;
    min-height: 44px;
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text);
    cursor: pointer;
  }

  .size output {
    min-width: 40px;
    text-align: center;
  }

  /* The orb status shows as a pill at the top of the panel, as in the mockup. */
  .column :global(.assistant .head) {
    display: inline-flex;
    align-self: flex-start;
    align-items: center;
    gap: var(--space-1);
    padding: 2px var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: 999px;
    background: var(--color-md-surface);
    color: var(--color-md-text);
    font-size: 9px;
  }

  .pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .pane[hidden] {
    display: none;
  }

  .pane > :global(.assistant) {
    background: transparent;
    border-left: none;
    padding: var(--space-2);
    flex: 1;
    min-height: 0;
    min-width: 0;
  }
</style>
