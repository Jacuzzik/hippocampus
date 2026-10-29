<script lang="ts">
  import "./control.css";
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import BudgetSection from "./BudgetSection.svelte";
  import KeysSection from "./KeysSection.svelte";
  import MemorySection from "./MemorySection.svelte";
  import NetworkSection from "./NetworkSection.svelte";
  import { SETTINGS_TABS, type SettingsTab } from "./model";

  // Settings in six tabs. The panels reuse the control panel sections, so each setting has one home.
  let { onclose }: { onclose: () => void } = $props();

  let tab = $state<SettingsTab>("General");
  let sidecar = $state<string>("Checking…");

  onMount(async () => {
    try {
      await invoke("sidecar_call", { method: "network" });
      sidecar = "Running";
    } catch (cause) {
      sidecar = `Not running: ${String(cause)}`;
    }
  });

  function onKey(e: KeyboardEvent): void {
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
    aria-label="Settings"
    tabindex="-1"
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    <header>
      <h2>Settings</h2>
      <button
        type="button"
        class="close"
        aria-label="Close settings"
        onclick={onclose}>×</button
      >
    </header>
    <div class="tabs" role="tablist" aria-label="Settings tabs">
      {#each SETTINGS_TABS as name (name)}
        <button
          type="button"
          role="tab"
          id={`tab-${name.replace(/\W+/g, "-").toLowerCase()}`}
          aria-selected={tab === name}
          aria-controls="settings-panel"
          tabindex={tab === name ? 0 : -1}
          onclick={() => (tab = name)}>{name}</button
        >
      {/each}
    </div>
    <div
      class="sections"
      role="tabpanel"
      id="settings-panel"
      aria-labelledby={`tab-${tab.replace(/\W+/g, "-").toLowerCase()}`}
    >
      {#if tab === "General"}
        <section class="control-section">
          <h3>General</h3>
          <dl class="facts">
            <dt>Theme</dt>
            <dd>Dark. The only theme in version 1.</dd>
            <dt>Settings file</dt>
            <dd>
              config/settings.toml. Edit it by hand, or here. Both are the same
              settings.
            </dd>
          </dl>
        </section>
      {:else if tab === "Prerequisites"}
        <section class="control-section">
          <h3>Prerequisites</h3>
          <dl class="facts">
            <dt>Python sidecar</dt>
            <dd>{sidecar}</dd>
            <dt>Local model (Ollama)</dt>
            <dd>Not set up: this build does not check for it.</dd>
          </dl>
        </section>
      {:else if tab === "Autonomy and budgets"}
        <NetworkSection />
        <BudgetSection />
      {:else if tab === "Integrations"}
        <KeysSection />
        <section class="control-section">
          <h3>Other integrations</h3>
          <p class="muted">
            Not set up: Slack, Notion and calendars are not connected in this
            build.
          </p>
        </section>
      {:else if tab === "Dictation and meeting"}
        <section class="control-section">
          <h3>Dictation and meeting</h3>
          <p class="muted">
            Not set up: dictation and meeting capture are not in this build.
          </p>
        </section>
      {:else}
        <MemorySection />
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

  .close {
    padding: 0 var(--space-2);
    color: var(--color-text-muted);
    font-size: var(--font-size-lg);
    background: none;
    border: 0;
    cursor: pointer;
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin: var(--space-3) 0;
  }

  .tabs button {
    padding: var(--space-1) var(--space-3);
    color: var(--color-text-muted);
    font: inherit;
    background: none;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .tabs button[aria-selected="true"] {
    color: var(--color-text);
    border-color: var(--color-text-subtle);
  }

  .sections {
    overflow-y: auto;
    padding-right: var(--space-2);
  }

  .facts {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }

  .facts dt {
    color: var(--color-text-muted);
  }

  .facts dd {
    margin: 0;
  }
</style>
