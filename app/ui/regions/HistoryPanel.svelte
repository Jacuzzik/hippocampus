<!-- Past office events, read only: settings changes, budget pauses, handoffs and errors. Tool runs stay in Activity. -->
<script lang="ts">
  import Loading from "../controls/Loading.svelte";
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { flagOn } from "../flags.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";

  type Row = { ts: string; kind: string; text?: string; method?: string };

  const PAST = ["setting", "budget", "handoff", "error"];

  let rows = $state<Row[]>([]);
  let failed = $state(false);
  let query = $state("");
  const shown = $derived(
    rows.filter((row) =>
      `${row.kind} ${row.text ?? row.method ?? ""}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
    ),
  );
  // False until the first answer (or failure), so an empty list is not shown while it is still loading.
  let loaded = $state(false);

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    try {
      const all = (
        await invoke<{ rows: Row[] }>("sidecar_call", { method: "activity" })
      ).rows;
      rows = all.filter((row) => PAST.includes(row.kind));
      failed = false;
      loaded = true;
    } catch (cause) {
      failed = true;
      loaded = true;
      console.error("Could not read the history", cause);
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });
</script>

<section class="history" aria-label="History">
  {#if !loaded}
    <Loading what="the history" />
  {:else if failed}
    <p class="muted">Could not read the history.</p>
  {:else if rows.length === 0}
    <p class="muted">No history yet.</p>
  {:else}
    <input
      type="search"
      class="find"
      aria-label="Search history"
      placeholder="Search history"
      bind:value={query}
    />
    {#if shown.length === 0}
      <p class="muted">No event matches "{query.trim()}".</p>
    {:else}
      <ul>
        {#each shown as row (row.ts + row.kind + (row.text ?? ""))}
          <li>
            <span class="kind">{row.kind}</span>
            <span class="text">{row.text ?? row.method ?? ""}</span>
            <small>{row.ts.replace("T", " ").slice(0, 19)}</small>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>

<style>
  .history {
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  .find {
    width: 100%;
    margin-bottom: var(--space-1);
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
