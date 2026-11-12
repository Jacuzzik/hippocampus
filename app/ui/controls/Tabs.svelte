<script lang="ts" module>
  export type TabItem = {
    id: string;
    label: string;
    badge?: number | string;
    disabled?: boolean;
    reason?: string;
  };
</script>

<script lang="ts">
  // One tab bar for the whole app. Arrow keys, Home and End move between tabs; a disabled tab says why.
  let {
    items,
    value = $bindable(),
    label,
    idBase,
    vertical = false,
    segmented = false,
    columns = 0,
    onchange,
  }: {
    items: TabItem[];
    value: string;
    label: string;
    idBase: string;
    vertical?: boolean;
    /** The joined pill look used in the Control Room and agent panels. */
    segmented?: boolean;
    /** Segmented only: tabs per row. 0 puts them all on one row. */
    columns?: number;
    /** Called after the user picks a tab, for a tab that also has to load something. */
    onchange?: (id: string) => void;
  } = $props();

  let bar: HTMLDivElement;

  // An element id cannot hold a space, and some tab ids do ("ask me").
  const tabId = (id: string): string =>
    `${idBase}-tab-${id.replace(/\W+/g, "-")}`;

  function pick(id: string): void {
    value = id;
    onchange?.(id);
  }

  function move(from: number, step: number): void {
    const count = items.length;
    for (let i = 1; i <= count; i++) {
      const next = items[(from + step * i + count * i) % count];
      if (next && !next.disabled) {
        pick(next.id);
        bar
          .querySelector<HTMLButtonElement>(`#${CSS.escape(tabId(next.id))}`)
          ?.focus();
        return;
      }
    }
  }

  function onKey(e: KeyboardEvent, index: number): void {
    const forward = vertical ? "ArrowDown" : "ArrowRight";
    const back = vertical ? "ArrowUp" : "ArrowLeft";
    if (e.key === forward) move(index, 1);
    else if (e.key === back) move(index, -1);
    else if (e.key === "Home") move(-1, 1);
    else if (e.key === "End") move(items.length, -1);
    else return;
    e.preventDefault();
  }
</script>

<div
  class="tabs"
  class:vertical
  class:segmented
  style:--tab-columns={segmented ? columns || items.length : null}
  role="tablist"
  aria-label={label}
  aria-orientation={vertical ? "vertical" : "horizontal"}
  bind:this={bar}
>
  {#each items as item, index (item.id)}
    <button
      type="button"
      role="tab"
      id={tabId(item.id)}
      aria-selected={value === item.id}
      aria-controls={`${idBase}-panel`}
      tabindex={value === item.id ? 0 : -1}
      disabled={item.disabled}
      title={item.disabled ? item.reason : undefined}
      onclick={() => pick(item.id)}
      onkeydown={(e) => onKey(e, index)}
    >
      <span>{item.label}</span>
      {#if item.badge !== undefined && item.badge !== 0 && item.badge !== ""}
        <span class="badge">{item.badge}</span>
      {/if}
    </button>
  {/each}
</div>

<style>
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .tabs.vertical {
    flex-direction: column;
    flex-wrap: nowrap;
  }

  button {
    display: inline-flex;
    gap: var(--space-2);
    align-items: center;
    justify-content: space-between;
    min-height: var(--layout-control-h);
    padding: var(--space-1) var(--space-3);
    color: var(--color-text-muted);
    font: inherit;
    font-size: var(--font-size-sm);
    text-align: left;
    background: none;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition:
      color 120ms ease,
      background-color 120ms ease,
      border-color 120ms ease;
  }

  button:hover:not(:disabled) {
    color: var(--color-text);
    border-color: var(--color-border);
  }

  button[aria-selected="true"] {
    color: var(--color-accent-on);
    background: var(--color-accent);
    border-color: var(--color-accent);
  }

  button:focus-visible {
    outline: 2px solid var(--color-focus-ring);
    outline-offset: 1px;
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Segmented: rows of joined cells, each row its own pill, in the Control Room colours. */
  .tabs.segmented {
    display: grid;
    grid-template-columns: repeat(var(--tab-columns), minmax(0, 1fr));
    gap: var(--space-2) 1px;
    padding: 1px;
  }

  .segmented button {
    justify-content: center;
    min-width: 0;
    min-height: 32px;
    padding: 0 var(--space-2);
    color: var(--color-md-text-muted);
    font-size: var(--font-size-xs);
    text-align: center;
    border: none;
    border-radius: 0;
    box-shadow: 0 0 0 1px var(--color-md-border);
  }

  .segmented button:hover:not(:disabled) {
    color: var(--color-md-text);
  }

  .segmented button[aria-selected="true"] {
    color: var(--color-md-accent-on);
    background: var(--color-md-accent);
    box-shadow: 0 0 0 1px var(--color-md-accent);
  }

  .segmented button > span:first-child {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .badge {
    padding: 0 var(--space-1);
    font-size: var(--font-size-tag);
    border: 1px solid currentColor;
    border-radius: var(--radius-sm);
  }

  @media (prefers-reduced-motion: reduce) {
    button {
      transition: none;
    }
  }
</style>
