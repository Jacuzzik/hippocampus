<script lang="ts">
  import "./control.css";
  import ActivitySection from "./ActivitySection.svelte";
  import ArchivedAgentsSection from "./ArchivedAgentsSection.svelte";
  import AsksSection from "./AsksSection.svelte";
  import BudgetSection from "./BudgetSection.svelte";
  import CapabilitiesSection from "./CapabilitiesSection.svelte";
  import DispatchSection from "./DispatchSection.svelte";
  import HelpersSection from "./HelpersSection.svelte";
  import JobsSection from "./JobsSection.svelte";
  import KeysSection from "./KeysSection.svelte";
  import MemorySection from "./MemorySection.svelte";
  import NetworkSection from "./NetworkSection.svelte";
  import ShareSection from "./ShareSection.svelte";
  import SkillsSection from "./SkillsSection.svelte";
  import TeamsSection from "./TeamsSection.svelte";
  import TriggersSection from "./TriggersSection.svelte";

  // The control panel: network, triggers, budgets, dispatch, the activity log, questions,
  // memory, jobs, helpers, capabilities, teams, sharing, skills and keys, in one scrolling list.
  let { onclose, onsettings }: { onclose: () => void; onsettings: () => void } =
    $props();

  function onKey(e: KeyboardEvent): void {
    // Stops here so the graph's own Escape (which clears the selection) does not also run.
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }
</script>

<div class="scrim" role="presentation" onmousedown={onclose}>
  <div
    class="box"
    role="dialog"
    aria-modal="true"
    aria-label="Control panel"
    tabindex="-1"
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    <header>
      <h2>Control panel</h2>
      <div class="actions">
        <button type="button" aria-label="Open settings" onclick={onsettings}
          >Settings</button
        >
        <button
          type="button"
          class="close"
          aria-label="Close control panel"
          onclick={onclose}>×</button
        >
      </div>
    </header>
    <div class="sections">
      <NetworkSection />
      <TriggersSection />
      <BudgetSection />
      <DispatchSection />
      <AsksSection />
      <ActivitySection />
      <MemorySection />
      <JobsSection />
      <HelpersSection />
      <CapabilitiesSection />
      <TeamsSection />
      <ArchivedAgentsSection />
      <ShareSection />
      <SkillsSection />
      <KeysSection />
    </div>
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 20;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--color-bg-0) 70%, transparent);
  }

  .box {
    display: flex;
    flex-direction: column;
    width: min(680px, calc(100vw - 2 * var(--space-4)));
    max-height: 85vh;
    padding: var(--space-5);
    color: var(--color-text);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    box-shadow: var(--layout-drawer-shadow);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-lg);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }

  .actions button {
    padding: var(--space-1) var(--space-3);
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .close {
    padding: 0 var(--space-2);
    color: var(--color-text-muted);
    font-size: var(--font-size-lg);
    background: none;
    border: 0;
    cursor: pointer;
  }

  .sections {
    overflow-y: auto;
    padding-right: var(--space-2);
  }
</style>
