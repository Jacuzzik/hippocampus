<script lang="ts">
  // Icon strip on the far left, as in Obsidian's ribbon. Each button shows or hides one pane.
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
    aria-label="Control panel"
    title="Control panel"
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
    aria-label="Setup and account"
    title="Setup and account"
    onclick={onaccount}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
    </svg>
  </button>
  <button
    type="button"
    class="bottom"
    aria-label="Settings"
    title="Settings"
    onclick={onsettings}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
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

  .bottom {
    margin-top: auto;
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
