<!-- Settings as a floating panel from the left ribbon, laid out like the Control panel. -->
<script lang="ts">
  import "../control/control.css";
  import SettingsPanel from "./SettingsPanel.svelte";

  let { onclose }: { onclose: () => void } = $props();

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
      <button type="button" class="close" aria-label="Close settings" onclick={onclose}>×</button>
    </header>
    <div class="sections">
      <SettingsPanel />
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

  .sections {
    overflow-y: auto;
    padding-right: var(--space-2);
  }
</style>
