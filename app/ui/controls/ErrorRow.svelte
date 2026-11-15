<script lang="ts">
  // What a list shows when its answer fails: the message, and a button to ask again.
  // The loader is replaced by this row, so a failure is never a silent spinner.
  let {
    message,
    onretry,
  }: { message: string; onretry?: () => void | Promise<void> } = $props();
</script>

<div class="error-row" role="alert">
  <p class="error">{message}</p>
  {#if onretry}
    <button type="button" class="retry" onclick={() => void onretry()}
      >Try again</button
    >
  {/if}
</div>

<style>
  .error-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .error-row p {
    margin: 0;
  }
  .retry {
    font: inherit;
    color: inherit;
    background: none;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }
</style>
