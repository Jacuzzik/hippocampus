<script lang="ts">
  import { matchFilter, tagCounts, type GraphData } from "../graph/model";

  // Search, tag and memory filters and note list. The graph reads the same state through props.
  let {
    data,
    query = $bindable(""),
    tag = $bindable<string | null>(null),
    memory = $bindable(false),
    selectedId = $bindable<string | null>(null),
    searchEl = $bindable<HTMLInputElement | null>(null),
  }: {
    data: GraphData;
    query?: string;
    tag?: string | null;
    memory?: boolean;
    selectedId?: string | null;
    searchEl?: HTMLInputElement | null;
  } = $props();

  const tags = $derived(tagCounts(data.nodes));
  const matched = $derived(matchFilter(data.nodes, { query, tag, memory }));
  const shown = $derived(data.nodes.filter((_, i) => matched[i]));

  function onSearchKey(e: KeyboardEvent): void {
    if (e.key !== "Enter" || !query.trim() || !shown[0]) return;
    selectedId = shown[0].id;
  }
</script>

<aside class="sidebar" aria-label="Notes">
  <header class="head">
    <h2>Hippocampus</h2>
    <span class="count" aria-live="polite"
      >{shown.length} of {data.nodes.length}</span
    >
  </header>

  <input
    type="search"
    bind:this={searchEl}
    bind:value={query}
    onkeydown={onSearchKey}
    placeholder="Search notes"
    aria-label="Search notes"
  />
  <button
    type="button"
    class="memory"
    aria-pressed={memory}
    onclick={() => (memory = !memory)}>Memory only</button
  >
  <select
    value={tag ?? ""}
    onchange={(e) => (tag = e.currentTarget.value || null)}
    aria-label="Filter by tag"
  >
    <option value="">All tags</option>
    {#each tags as [t] (t)}
      <option value={t}>#{t}</option>
    {/each}
  </select>

  <details class="tags-pane" open>
    <summary>Tags</summary>
    <ul aria-label="Tags">
      {#each tags as [t, count] (t)}
        <li>
          <button
            type="button"
            class="tag"
            aria-pressed={tag === t}
            onclick={() => (tag = tag === t ? null : t)}
            >#{t} <span class="count">{count}</span></button
          >
        </li>
      {:else}
        <li class="muted">No tags yet.</li>
      {/each}
    </ul>
  </details>

  <ul class="notes" aria-label="Note list">
    {#each shown as node (node.id)}
      <li>
        <button
          type="button"
          class="note"
          aria-current={node.id === selectedId ? "true" : undefined}
          onclick={() => (selectedId = node.id)}>{node.title}</button
        >
      </li>
    {:else}
      <li class="muted">No notes match.</li>
    {/each}
  </ul>
</aside>

<style>
  .sidebar {
    grid-area: sidebar;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-width: 0;
    min-height: 0;
    padding: var(--space-3);
    background: var(--color-bg-1);
    border-right: 1px solid var(--color-border);
    color: var(--color-text);
  }

  .head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-sm);
  }

  .count,
  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  input,
  select {
    font: inherit;
    min-width: 0;
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
  }

  .memory {
    font: inherit;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }

  .memory[aria-pressed="true"] {
    color: var(--color-text);
    border-color: var(--color-text-muted);
  }

  .tags-pane summary {
    cursor: pointer;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .tags-pane ul {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin: var(--space-1) 0 0;
    padding: 0;
    list-style: none;
    max-height: 7rem;
    overflow-y: auto;
  }

  .tag {
    font: inherit;
    font-size: var(--font-size-xs);
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: 0 var(--space-1);
    cursor: pointer;
  }

  .tag[aria-pressed="true"] {
    color: var(--color-link);
    border-color: var(--color-link);
  }

  .tag .count {
    color: var(--color-text-muted);
  }

  .notes {
    flex: 1;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    list-style: none;
  }

  .note {
    width: 100%;
    font: inherit;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--color-text);
    background: none;
    border: 0;
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }

  .note:hover {
    background: var(--color-surface);
  }

  .note[aria-current="true"] {
    color: var(--color-link);
    background: var(--color-surface);
  }

  .notes .muted {
    padding: var(--space-1) var(--space-2);
  }
</style>
