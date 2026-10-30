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

  type Watcher = {
    name: string;
    kind: string;
    status: "running" | "stopped" | "error";
    last_event: string | null;
  };

  let mode = $state<NetworkMode | null>(null);
  let budget = $state<Budget | null>(null);
  let watchers = $state<Watcher[]>([]);
  let failed = $state(false);

  onMount(async () => {
    try {
      mode = (await invoke<{ mode: NetworkMode }>("sidecar_call", { method: "network" })).mode;
      budget = await invoke<Budget>("sidecar_call", { method: "budget" });
      watchers = (await invoke<{ watchers: Watcher[] }>("sidecar_call", { method: "watchers" })).watchers;
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
    <h3>Watchers</h3>
    {#if watchers.length === 0}
      <p class="muted">No background watchers are set up.</p>
    {:else}
      <ul>
        {#each watchers as watcher, i (i)}
          <li>
            <span class="status {watcher.status}">{watcher.status}</span>
            {watcher.name}
            <span class="muted">{watcher.kind}{watcher.last_event ? `, last ${watcher.last_event}` : ""}</span>
          </li>
        {/each}
      </ul>
    {/if}
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

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    padding: var(--space-1) 0;
  }

  .status {
    display: inline-block;
    min-width: 6ch;
    color: var(--color-md-text-muted);
  }

  .status.running {
    color: var(--color-md-accent);
  }

  .status.error {
    color: var(--color-md-danger);
  }
</style>
