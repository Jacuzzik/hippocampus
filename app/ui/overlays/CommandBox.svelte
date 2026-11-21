<script module lang="ts">
  // One item to pick: a note for the quick switcher, an action for the command palette.
  export type Item = {
    id: string;
    label: string;
    hint?: string;
    run: () => void;
  };
</script>

<script lang="ts">
  import Dialog from "../controls/Dialog.svelte";
  import { onMount } from "svelte";
  import { fuzzyScore } from "../fuzzy";

  // One box for both the quick switcher (notes) and the command palette (actions), as in notes app.

  let {
    items,
    placeholder,
    label,
    onclose,
  }: {
    items: Item[];
    placeholder: string;
    label: string;
    onclose: () => void;
  } = $props();

  let query = $state("");
  let active = $state(0);
  let input: HTMLInputElement | null = $state(null);

  const shown = $derived(
    items
      .map((item) => ({ item, score: fuzzyScore(query, item.label) }))
      .filter((m): m is { item: Item; score: number } => m.score !== null)
      .sort((a, b) => b.score - a.score)
      .map((m) => m.item),
  );

  $effect(() => {
    void query;
    active = 0;
  });

  onMount(() => input?.focus());

  function choose(item: Item | undefined): void {
    if (!item) return;
    onclose();
    item.run();
  }

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      // Stops here so the graph's own Escape (which clears the selection) does not also run.
      e.stopPropagation();
      onclose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      active = Math.min(active + 1, shown.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      active = Math.max(active - 1, 0);
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(shown[active]);
    }
  }
</script>

<Dialog title={label} {onclose} bare>
  <input
    bind:this={input}
    bind:value={query}
    onkeydown={onKey}
    {placeholder}
    aria-label={label}
    autocomplete="off"
    role="combobox"
    aria-expanded="true"
    aria-controls="command-box-list"
    aria-activedescendant={shown[active] ? `command-box-${active}` : undefined}
  />
  <ul id="command-box-list" role="listbox" aria-label="Matches">
    {#each shown as item, i (item.id)}
      <li role="presentation">
        <button
          type="button"
          id="command-box-{i}"
          role="option"
          tabindex="-1"
          aria-selected={i === active}
          class:active={i === active}
          onmouseenter={() => (active = i)}
          onclick={() => choose(item)}
        >
          <span>{item.label}</span>
          {#if item.hint}<span class="hint">{item.hint}</span>{/if}
        </button>
      </li>
    {:else}
      <li class="muted" role="presentation">No matches.</li>
    {/each}
  </ul>
</Dialog>

<style>
  input {
    font: inherit;
    min-width: 0;
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
  }

  ul {
    margin: 0;
    padding: 0;
    overflow-y: auto;
    list-style: none;
  }

  button {
    width: 100%;
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    font: inherit;
    text-align: left;
    color: var(--color-text);
    background: none;
    border: 0;
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }

  button.active {
    background: var(--color-surface);
    color: var(--color-link);
  }

  .hint,
  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .muted {
    cursor: default;
  }
</style>
