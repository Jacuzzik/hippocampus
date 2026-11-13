<script lang="ts">
  // Tokens the app used today against its daily cap, in the status bar. Click opens Settings, Budgets.
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { meter } from "../spend.ts";

  type Budget = {
    caps: { app: { daily: number } };
    used: { app: { daily: number } };
  };
  let budget = $state<Budget | null>(null);

  async function load(): Promise<void> {
    try {
      budget = await invoke<Budget>("sidecar_call", { method: "budget" });
    } catch {
      // The meter is a convenience; Settings, Budgets shows the failure if it matters.
      budget = null;
    }
  }
  onMount(() => {
    void load();
    return every(load, 30000);
  });

  const shown = $derived(
    budget ? meter(budget.used.app.daily, budget.caps.app.daily) : null,
  );
</script>

{#if shown}
  <button
    type="button"
    class="spend {shown.level}"
    aria-label={`Tokens used today: ${shown.text}. Open Budgets`}
    onclick={() =>
      window.dispatchEvent(
        new CustomEvent("open-settings", { detail: "Budgets" }),
      )}>{shown.text}</button
  >
{/if}

<style>
  .spend {
    flex: none;
    min-height: var(--space-5);
    padding: 0 var(--space-2);
    color: var(--color-text-muted);
    font: inherit;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .spend:hover {
    border-color: var(--color-border);
  }

  .near {
    color: var(--color-ds-warning);
  }

  .over {
    color: var(--color-danger);
  }
</style>
