<nav class="left-rail" aria-label="Navigation">
  {#each [1, 2, 3] as slot (slot)}
    <div class="slot" aria-hidden="true"></div>
  {/each}
</nav>

<style>
  .left-rail {
    grid-area: rail;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) 0;
    background: var(--color-bg-1);
    border-right: 1px solid var(--color-border);
  }

  .slot {
    width: calc(var(--layout-left-rail-width) - 2 * var(--space-3));
    aspect-ratio: 1;
    border-radius: var(--radius-md);
    background: var(--color-surface);
  }
</style>
