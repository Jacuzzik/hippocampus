<script lang="ts">
  // What a list shows when it has nothing: what it is for, why it is empty, and one thing to do next.
  let {
    title,
    text = "",
    action = "",
    onaction,
  }: {
    title: string;
    text?: string;
    action?: string;
    onaction?: () => void;
  } = $props();
</script>

<div class="empty">
  <b>{title}</b>
  {#if text}<p>{text}</p>{/if}
  {#if action && onaction}<button type="button" onclick={onaction}
      >{action}</button
    >{/if}
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    align-items: flex-start;
    padding: var(--space-3);
    color: var(--color-text);
    font-size: var(--font-size-sm);
    border: 1px dashed var(--color-border);
    border-radius: var(--radius-sm);
  }

  p {
    margin: 0;
    color: var(--color-text-muted);
  }

  button {
    padding: var(--space-1) var(--space-3);
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }
</style>
