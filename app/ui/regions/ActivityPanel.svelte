<!-- The live activity log, read only: tool runs, approvals and errors, newest first. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";

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

  onMount(async () => {
    try {
      rows = (await invoke<{ rows: Row[] }>("sidecar_call", { method: "activity" })).rows;
    } catch (cause) {
      failed = true;
      console.error("Could not read the activity log", cause);
    }
  });

  const label = (row: Row) =>
    row.text ?? [row.tool, row.tier, row.approved ? "approved" : row.status].filter(Boolean).join(" · ");
</script>

<section class="activity" aria-label="Activity">
  {#if failed}
    <p class="muted">Could not read the activity log.</p>
  {:else if rows.length === 0}
    <p class="muted">No activity yet.</p>
  {:else}
    <ul>
      {#each rows as row (row.ts + row.kind + label(row))}
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
    font-family: var(--font-mono);
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
