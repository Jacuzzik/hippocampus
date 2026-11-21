<!-- 2.09 First run: with no Claude login or key and no Ollama answering, say so, with the two ways forward. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";

  // Nothing shows until the first answer, so the notice never flashes while the backend starts.
  let loaded = $state(false);
  let nothingSetUp = $state(false);

  async function check(): Promise<void> {
    try {
      const a = await invoke<{ ready: boolean; local?: boolean }>(
        "sidecar_call",
        { method: "account" },
      );
      nothingSetUp = !a.ready && a.local === false;
    } catch {
      nothingSetUp = false; // the backend not answering is shown elsewhere
    } finally {
      loaded = true;
    }
  }
  onMount(() => {
    void check();
    window.addEventListener("engine-changed", check);
    return () => window.removeEventListener("engine-changed", check);
  });
</script>

{#if loaded && nothingSetUp}
  <section class="first-run" aria-label="No model set up">
    <h3>No model is set up yet</h3>
    <p>
      There is no Claude login or key, and Ollama is not running on this
      computer. Add a key, or install Ollama to run a model here for free.
    </p>
    <div class="actions">
      <button
        type="button"
        onclick={() =>
          window.dispatchEvent(
            new CustomEvent("open-settings", { detail: "Models and keys" }),
          )}>Add a key</button
      >
      <a
        href="https://ollama.com/download"
        target="_blank"
        rel="noopener noreferrer">Install Ollama</a
      >
    </div>
  </section>
{/if}

<style>
  .first-run {
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-2);
  }
  h3 {
    margin: 0 0 var(--space-1);
    font-size: var(--font-size-sm);
  }
  p {
    margin: 0 0 var(--space-2);
    font-size: var(--font-size-sm);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
</style>
