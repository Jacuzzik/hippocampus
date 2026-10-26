<!-- The owner's view: cards the main agent fills (numbers, analytics, anything for the owner). -->
<section class="owner-panel" aria-label="Owner panel">
  <p class="empty">No cards yet.</p>
</section>

<style>
  .owner-panel {
    display: flex;
    flex-direction: column;
    height: 35%;
    min-height: 8rem;
    padding: var(--space-3);
    border-top: 1px solid var(--color-border);
    overflow: auto;
  }

  .empty {
    margin: auto;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }
</style>
