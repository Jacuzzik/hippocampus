<!-- Past office events, read only: settings changes, budget pauses, handoffs and errors. Tool runs stay in Activity. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { flagOn } from "../flags.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";

  type Row = { ts: string; kind: string; text?: string; method?: string };

  const PAST = ["setting", "budget", "handoff", "error"];

  let rows = $state<Row[]>([]);
  let failed = $state(false);

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    try {
      const all = (await invoke<{ rows: Row[] }>("sidecar_call", { method: "activity" })).rows;
      rows = all.filter((row) => PAST.includes(row.kind));
      failed = false;
    } catch (cause) {
      failed = true;
      console.error("Could not read the history", cause);
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });
</script>

<section class="history" aria-label="History">
  {#if failed}
    <p class="muted">Could not read the history.</p>
  {:else if rows.length === 0}
    <p class="muted">No history yet.</p>
  {:else}
    <ul>
      {#each rows as row (row.ts + row.kind + (row.text ?? ""))}
        <li>
          <span class="kind">{row.kind}</span>
          <span class="text">{row.text ?? row.method ?? ""}</span>
          <small>{row.ts.replace("T", " ").slice(0, 19)}</small>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .history {
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .kind {
    color: var(--color-md-accent);
  }

  .text {
    color: var(--color-md-text-muted);
  }

  li small {
    margin-left: auto;
    color: var(--color-md-text-subtle);
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
