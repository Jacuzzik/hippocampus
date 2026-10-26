<script lang="ts">
  // Icon strip on the far left, as in Obsidian's ribbon. Each button shows or hides one pane.
  let {
    sidebarOpen = $bindable(true),
    panelOpen = $bindable(true),
    onaccount,
  }: {
    sidebarOpen?: boolean;
    panelOpen?: boolean;
    onaccount: () => void;
  } = $props();
</script>

<nav class="ribbon" aria-label="Panes">
  <button
    type="button"
    aria-label="Note list"
    aria-pressed={sidebarOpen}
    title="Note list"
    onclick={() => (sidebarOpen = !sidebarOpen)}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <line x1="9" y1="4" x2="9" y2="20" />
    </svg>
  </button>
  <button
    type="button"
    aria-label="Assistant"
    aria-pressed={panelOpen}
    title="Assistant"
    onclick={() => (panelOpen = !panelOpen)}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <line x1="15" y1="4" x2="15" y2="20" />
    </svg>
  </button>
  <button
    type="button"
    aria-label="Setup and account"
    title="Setup and account"
    onclick={onaccount}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
    </svg>
  </button>
</nav>

<style>
  .ribbon {
    grid-area: rail;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) 0;
    background: var(--color-bg-1);
    border-right: 1px solid var(--color-border);
  }

  button {
    display: grid;
    place-items: center;
    width: calc(var(--layout-ribbon-width) - 2 * var(--space-2));
    aspect-ratio: 1;
    padding: 0;
    color: var(--color-text-muted);
    background: none;
    border: 0;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  button:hover {
    color: var(--color-text);
    background: var(--color-surface);
  }

  button[aria-pressed="true"] {
    color: var(--color-text);
  }

  svg {
    width: 18px;
    height: 18px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
  }
</style>
