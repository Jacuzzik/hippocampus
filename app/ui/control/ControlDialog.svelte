<script lang="ts">
  import { dialogFocus } from "../controls/dialogFocus.ts";
  import "./control.css";
  import ActivitySection from "./ActivitySection.svelte";
  import ArchivedAgentsSection from "./ArchivedAgentsSection.svelte";
  import AsksSection from "./AsksSection.svelte";
  import CapabilitiesSection from "./CapabilitiesSection.svelte";
  import DispatchSection from "./DispatchSection.svelte";
  import HelpersSection from "./HelpersSection.svelte";
  import JobsSection from "./JobsSection.svelte";
  import NetworkSection from "./NetworkSection.svelte";
  import ShareSection from "./ShareSection.svelte";
  import SkillsSection from "./SkillsSection.svelte";
  import TeamsSection from "./TeamsSection.svelte";
  import TriggersSection from "./TriggersSection.svelte";
  import Tabs from "../controls/Tabs.svelte";

  // The control panel: day-to-day operations in five tabs. Budgets, memory and keys are settings,
  // so they live in Settings (the button at the top), each in one place.
  let { onclose, onsettings }: { onclose: () => void; onsettings: () => void } =
    $props();

  const TABS = [
    { id: "overview", label: "Overview" },
    { id: "work", label: "Work" },
    { id: "questions", label: "Questions" },
    { id: "skills", label: "Helpers and skills" },
    { id: "team", label: "Team and sharing" },
  ];
  let tab = $state("overview");

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
    use:dialogFocus
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
    <div class="tabbar">
      <Tabs
        items={TABS}
        bind:value={tab}
        label="Control panel tabs"
        idBase="control"
      />
    </div>
    <div
      class="sections"
      role="tabpanel"
      id="control-panel"
      aria-labelledby={`control-tab-${tab}`}
      tabindex="-1"
    >
      {#if tab === "overview"}
        <NetworkSection />
        <ActivitySection />
      {:else if tab === "work"}
        <DispatchSection />
        <JobsSection />
        <TriggersSection />
      {:else if tab === "questions"}
        <AsksSection />
      {:else if tab === "skills"}
        <HelpersSection />
        <CapabilitiesSection />
        <SkillsSection />
      {:else}
        <TeamsSection />
        <ArchivedAgentsSection />
        <ShareSection />
      {/if}
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
    height: min(640px, 85vh);
    padding: var(--space-4);
    color: var(--color-text);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    border-radius: var(--radius-sm);
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

  .tabbar {
    margin: var(--space-3) 0 var(--space-1);
  }

  .sections {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding-right: var(--space-2);
  }
</style>
