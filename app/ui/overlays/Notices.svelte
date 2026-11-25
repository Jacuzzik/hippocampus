<!-- Failed actions, said on screen: each line names what failed and why, and goes away on its own. -->
<script lang="ts">
  import { notices } from "../notices.svelte.ts";
</script>

<div class="notices" role="alert" aria-label="Problems">
  {#each notices.list as notice (notice.id)}
    <div class="notice">
      <p>
        <b>{notice.what}.</b>
        {#if notice.detail}<span>{notice.detail}</span>{/if}
      </p>
      <button
        type="button"
        aria-label="Dismiss"
        onclick={() => notices.dismiss(notice.id)}>×</button
      >
    </div>
  {/each}
</div>

<style>
  .notices {
    position: fixed;
    inset-inline-end: var(--space-4);
    bottom: var(--space-4);
    z-index: 90; /* above every dialog: a failure inside a dialog must stay readable */
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    width: min(360px, calc(100vw - 2 * var(--space-4)));
    pointer-events: none;
  }

  .notice {
    display: flex;
    gap: var(--space-2);
    align-items: flex-start;
    padding: var(--space-2) var(--space-3);
    color: var(--color-text);
    font-family: var(--font-ui);
    font-size: var(--font-size-sm);
    background: var(--pop-bg);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-danger);
    border-radius: var(--radius-sm);
    box-shadow: var(--layout-drawer-shadow);
    pointer-events: auto;
  }

  p {
    flex: 1;
    min-width: 0;
    margin: 0;
    overflow-wrap: anywhere;
  }

  span {
    color: var(--color-text-muted);
  }

  button {
    min-width: var(--size-24);
    min-height: var(--size-24);
    color: var(--color-text-muted);
    font: inherit;
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }
</style>
