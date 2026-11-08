<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";

  // Setup: the brain is the default vault the app creates on first start. Removing data keeps the notes.
  let { onclose }: { onclose: () => void; onopened?: () => void } = $props();

  let error = $state<string | null>(null);
  let confirmRemove = $state(false);
  let notice = $state<string | null>(null);

  async function removeData(): Promise<void> {
    if (!confirmRemove) {
      confirmRemove = true;
      return;
    }
    confirmRemove = false;
    error = null;
    notice = null;
    try {
      await invoke("sidecar_call", { method: "remove_data" });
      notice = "Removed the index cache. Your notes are untouched.";
    } catch (cause) {
      error = String(cause);
    }
  }

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
    aria-label="Setup"
    tabindex="-1"
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    <h2>Setup</h2>

    <div class="section">
      <h3>Your data</h3>
      <p class="muted">
        Removes the index cache. Your notes are never deleted.
      </p>
      <div>
        <button type="button" onclick={removeData}>
          {confirmRemove
            ? "Press again to remove Hippocampus data"
            : "Remove Hippocampus data"}
        </button>
      </div>
      {#if notice}
        <p class="muted">{notice}</p>
      {/if}
    </div>

    {#if error}
      <p role="alert" class="error">{error}</p>
    {/if}
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 10;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding-top: 12vh;
  }

  .box {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    width: min(560px, 90vw);
    padding: var(--space-4);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    border-radius: var(--radius-sm);
    color: var(--color-text);
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-sm);
  }

  h3 {
    margin: 0;
    font-size: var(--font-size-sm);
  }

  p {
    margin: var(--space-1) 0;
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  button {
    font: inherit;
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-3);
    cursor: pointer;
  }

  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .error {
    color: var(--color-text);
  }
</style>
