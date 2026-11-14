<script lang="ts">
  // Icon strip on the far left, as in the notes app's ribbon. Each button shows or hides one pane.
  let {
    sidebarOpen = $bindable(true),
    panelOpen = $bindable(true),
    onaccount,
    oncontrol,
    onsettings,
  }: {
    sidebarOpen?: boolean;
    panelOpen?: boolean;
    onaccount: () => void;
    oncontrol: () => void;
    onsettings: () => void;
  } = $props();
</script>

<nav class="ribbon" aria-label="Panes">
  <button
    type="button"
    aria-label="Note list"
    aria-pressed={sidebarOpen}
    data-tip="Note list"
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
    data-tip="Assistant"
    onclick={() => (panelOpen = !panelOpen)}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <line x1="15" y1="4" x2="15" y2="20" />
    </svg>
  </button>
  <button
    type="button"
    aria-label="Control panel"
    data-tip="Control panel"
    onclick={oncontrol}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="17" x2="20" y2="17" />
      <circle cx="9" cy="7" r="2.2" />
      <circle cx="15" cy="17" r="2.2" />
    </svg>
  </button>
  <button
    type="button"
    aria-label="Settings"
    data-tip="Settings · Ctrl+,"
    onclick={onsettings}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path
        d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"
      />
    </svg>
  </button>
  <button
    type="button"
    aria-label="Setup and account"
    data-tip="Setup and account"
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
