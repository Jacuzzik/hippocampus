<!-- The live activity log, read only: tool runs, approvals and errors, newest first. -->
<script lang="ts">
  import Loading from "../controls/Loading.svelte";
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { flagOn } from "../flags.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";
  import Toggle from "../controls/Toggle.svelte";

  type Row = {
    ts: string;
    kind: string;
    text?: string;
    tool?: string;
    tier?: string;
    status?: string;
    approved?: boolean;
  };

  let rows = $state<Row[]>([]);
  let failed = $state(false);
  // False until the first answer (or failure), so an empty list is not shown while it is still loading.
  let loaded = $state(false);
  // Filters: a kind (all by default), a word in the line, and a pause switch that stops the refresh.
  let kind = $state("all");
  let word = $state("");
  // A date range (YYYY-MM-DD, both ends included); empty means no limit on that side.
  let from = $state("");
  let to = $state("");
  let paused = $state(false);
  const kinds = $derived([...new Set(rows.map((row) => row.kind))].sort());

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    if (paused && loaded) return;
    try {
      rows = (
        await invoke<{ rows: Row[] }>("sidecar_call", { method: "activity" })
      ).rows;
      failed = false;
      loaded = true;
    } catch (cause) {
      failed = true;
      loaded = true;
      console.error("Could not read the activity log", cause);
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });

  const label = (row: Row) =>
    row.text ??
    [row.tool, row.tier, row.approved ? "approved" : row.status]
      .filter(Boolean)
      .join(" · ");
  const shown = $derived(
    rows.filter(
      (row) =>
        (kind === "all" || row.kind === kind) &&
        (!from || row.ts.slice(0, 10) >= from) &&
        (!to || row.ts.slice(0, 10) <= to) &&
        label(row).toLowerCase().includes(word.trim().toLowerCase()),
    ),
  );
</script>

<section class="activity" aria-label="Activity">
  {#if !loaded}
    <Loading what="the activity log" />
  {:else if failed}
    <p class="muted">Could not read the activity log.</p>
  {:else if rows.length === 0}
    <p class="muted">No activity yet.</p>
  {:else}
    <div class="filters">
      <select aria-label="Filter by kind" bind:value={kind}>
        <option value="all">All kinds</option>
        {#each kinds as k (k)}<option value={k}>{k}</option>{/each}
      </select>
      <input
        type="search"
        aria-label="Search activity"
        placeholder="Search activity"
        bind:value={word}
      />
      <label class="date"
        >From <input
          type="date"
          aria-label="From date"
          bind:value={from}
        /></label
      >
      <label class="date"
        >To <input type="date" aria-label="To date" bind:value={to} /></label
      >
      <Toggle bind:checked={paused} label="Pause" />
    </div>
    {#if shown.length === 0}
      <p class="muted">Nothing matches.</p>
    {/if}
    <ul>
      {#each shown as row (row.ts + row.kind + label(row))}
        <li>
          <span class="kind {row.kind}">{row.kind}</span>
          <span class="text">{label(row)}</span>
          <small>{row.ts.replace("T", " ").slice(0, 19)}</small>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .activity {
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    padding-bottom: var(--space-2);
  }

  .filters input[type="search"] {
    flex: 1;
    min-width: 0;
  }

  .filters .date {
    display: flex;
    gap: var(--space-1);
    align-items: center;
    color: var(--color-md-card-muted);
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

  .kind.error {
    color: var(--color-md-text);
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
