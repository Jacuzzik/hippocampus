<script lang="ts">
  import Button from "../controls/Button.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import Loading from "../controls/Loading.svelte";
  import {
    ACTIVITY_FILTERS,
    activityText,
    filterActivity,
    type ActivityKind,
    type ActivityRow,
  } from "./model";

  // One list of handoffs, tool calls, approvals, errors and settings changes, newest first.
  let rows = $state<ActivityRow[]>([]);
  let filter = $state<"all" | ActivityKind>("all");
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    try {
      const result = await invoke<{ rows: ActivityRow[] }>("sidecar_call", {
        method: "activity",
        params: { limit: 200 },
      });
      rows = result.rows;
    } catch (cause) {
      error = String(cause);
    }
  }

  const shown = $derived(filterActivity(rows, filter));

  // False until the first answer, so the loader shows and an empty list is not claimed too early.
  let loaded = $state(false);
  onMount(() => void load().finally(() => (loaded = true)));
</script>

<section class="control-section" aria-labelledby="control-activity">
  <h3 id="control-activity">Activity log</h3>
  <p class="hint">
    What the app and the assistant did. Approvals name the card that decided.
    Note text, previews and keys are never logged.
  </p>
  <div class="row" role="group" aria-label="Filter activity">
    {#each ACTIVITY_FILTERS as option (option.id)}
      <button
        type="button"
        class="segment"
        aria-pressed={filter === option.id}
        onclick={() => (filter = option.id)}>{option.label}</button
      >
    {/each}
    <Button onclick={load}>Refresh</Button>
  </div>
  {#if !loaded}
    <Loading what="the activity log" />
  {:else if shown.length === 0}
    <p class="muted">Nothing here yet.</p>
  {:else}
    <ul aria-label="Activity">
      {#each shown as row, i (row.ts + row.kind + i)}
        <li>
          <span class="badge">{row.kind}</span>
          <span class="mono">{row.ts.slice(11, 19)}</span>
          {activityText(row)}
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
