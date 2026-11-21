<script lang="ts">
  import Button from "../controls/Button.svelte";
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
      <Button disabled={busy} onclick={removeData}>
        {busy
          ? "Removing…"
          : confirmRemove
            ? "Press again to remove Hippocampus data"
            : "Remove Hippocampus data"}
      </Button>
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

  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .error {
    color: var(--color-text);
  }
</style>
