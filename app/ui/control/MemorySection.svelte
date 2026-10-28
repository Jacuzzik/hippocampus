<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";

  // Search the assistant's memory notes. Text search always works. Search by meaning
  // needs an embedding model, which is not installed yet, so it shows "Not set up".
  type MemoryStatus = { ready: boolean; reason: string; max_bytes: number };
  type Hits = {
    mode: "text" | "meaning";
    hits: (string | { path: string; score: number })[];
  };

  let status = $state<MemoryStatus | null>(null);
  let mode = $state<"text" | "meaning">("text");
  let query = $state("");
  let results = $state<string[] | null>(null);
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    try {
      status = await invoke<MemoryStatus>("sidecar_call", {
        method: "memory_status",
      });
    } catch (cause) {
      error = String(cause);
    }
  }

  async function search(): Promise<void> {
    error = null;
    try {
      const found = await invoke<Hits>("sidecar_call", {
        method: "memory_search",
        params: { query, mode },
      });
      results = found.hits.map((hit) =>
        typeof hit === "string"
          ? hit
          : `${hit.path} (${Math.round(hit.score * 100)}%)`,
      );
    } catch (cause) {
      error = String(cause);
    }
  }

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-memory">
  <h3 id="control-memory">Memory search</h3>
  <p class="hint">
    Search the assistant's memory notes. Long memory notes are trimmed on open:
    the oldest sections move to an archive note, which keeps an index link.
  </p>
  <div class="row" role="group" aria-label="Search mode">
    <button
      type="button"
      class="segment"
      aria-pressed={mode === "text"}
      onclick={() => (mode = "text")}>By text</button
    >
    <button
      type="button"
      class="segment"
      aria-pressed={mode === "meaning"}
      disabled={!status?.ready}
      onclick={() => (mode = "meaning")}>By meaning</button
    >
    {#if status && !status.ready}
      <span class="badge" title={status.reason}>Not set up</span>
    {/if}
  </div>
  {#if status && !status.ready}
    <p class="hint">{status.reason}</p>
  {/if}
  <form
    class="row"
    onsubmit={(e) => {
      e.preventDefault();
      void search();
    }}
  >
    <input
      type="text"
      aria-label="Search memory"
      placeholder="Search memory notes"
      bind:value={query}
    />
    <button type="submit" class="primary">Search</button>
  </form>
  {#if results}
    {#if results.length === 0}
      <p class="muted">No memory notes match.</p>
    {:else}
      <ul aria-label="Memory results">
        {#each results as path (path)}
          <li class="mono">{path}</li>
        {/each}
      </ul>
    {/if}
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
