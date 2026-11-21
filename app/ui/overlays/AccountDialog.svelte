<script lang="ts">
  import Dialog from "../controls/Dialog.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import SetupChecklist from "./SetupChecklist.svelte";

  // Setup: the brain is the default vault the app creates on first start. Removing data keeps the notes.
  let { onclose }: { onclose: () => void; onopened?: () => void } = $props();

  let error = $state<string | null>(null);
  let confirmRemove = $state(false);
  let notice = $state<string | null>(null);

  // True while the removal runs (13.03).
  let busy = $state(false);
  async function removeData(): Promise<void> {
    if (!confirmRemove) {
      confirmRemove = true;
      return;
    }
    confirmRemove = false;
    error = null;
    notice = null;
    busy = true;
    try {
      await invoke("sidecar_call", { method: "remove_data" });
      notice = "Removed the index cache. Your notes are untouched.";
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
</script>

<Dialog title="Setup and account" {onclose}>
  <div class="section">
    <h3>Setup checks</h3>
    <SetupChecklist />
  </div>

  <div class="section">
    <h3>Your data</h3>
    <p class="muted">Removes the index cache. Your notes are never deleted.</p>
    <div>
      <button type="button" disabled={busy} onclick={removeData}>
        {busy
          ? "Removing…"
          : confirmRemove
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
</Dialog>

<style>
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
