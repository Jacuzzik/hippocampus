<!-- What the assistant may reach right now and what it has used, read only. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import {
    NETWORK_TEXT,
    WINDOWS,
    WINDOW_LABELS,
    usageLine,
    type Caps,
    type NetworkMode,
  } from "../control/model";

  type Budget = { caps: { app: Caps; assistant: Caps }; used: { app: Caps; assistant: Caps } };
  const SCOPES = [
    ["app", "Whole app"],
    ["assistant", "Assistant"],
  ] as const;

  let mode = $state<NetworkMode | null>(null);
  let budget = $state<Budget | null>(null);
  let failed = $state(false);

  onMount(async () => {
    try {
      mode = (await invoke<{ mode: NetworkMode }>("sidecar_call", { method: "network" })).mode;
      budget = await invoke<Budget>("sidecar_call", { method: "budget" });
    } catch (cause) {
      failed = true;
      console.error("Could not read the monitor", cause);
    }
  });
</script>

<section class="monitor" aria-label="Monitor">
  {#if failed}
    <p class="muted">Could not read the monitor.</p>
  {:else if !mode || !budget}
    <p class="muted">Checking…</p>
  {:else}
    <h3>Network</h3>
    <p>{mode}: {NETWORK_TEXT[mode]}</p>
    {#each SCOPES as [scope, label] (scope)}
      <h3>{label}</h3>
      <dl>
        {#each WINDOWS as window (window)}
          <dt>{WINDOW_LABELS[window]}</dt>
          <dd>{usageLine(budget.used[scope][window], budget.caps[scope][window])}</dd>
        {/each}
      </dl>
    {/each}
  {/if}
</section>

<style>
  .monitor {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  h3 {
    margin: var(--space-2) 0 var(--space-1);
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
    color: var(--color-md-accent);
  }

  p {
    margin: 0;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: var(--space-1) var(--space-2);
    margin: 0;
  }

  dt {
    color: var(--color-md-text-muted);
  }

  dd {
    margin: 0;
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
