<script lang="ts">
  // The heading of a section inside a panel: small capitals, a rule under it, and a count or note on the right.
  // Every panel uses this one, so the heading font, colour and spacing are written once.
  let { title, aside = "" }: { title: string; aside?: string } = $props();
</script>

<h3 class="panel-header">
  {title}{#if aside}<em>{aside}</em>{/if}
</h3>

<style>
  .panel-header {
    margin: 0;
    padding-bottom: var(--space-1);
    border-bottom: 1px solid var(--color-md-text-muted);
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
    font-weight: 400;
    color: var(--color-md-accent);
  }

  /* A heading that follows content (the next group in a list) gets air above it. */
  .panel-header:not(:first-child) {
    margin-top: var(--space-2);
  }

  em {
    margin-left: auto;
    font-style: normal;
    font-size: var(--font-size-xs);
    color: var(--color-md-text-muted);
  }
</style>
