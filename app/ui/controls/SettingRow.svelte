<script lang="ts">
  // One row of a Settings page: what it is called, one line of help, and the control on the right.
  import type { Snippet } from "svelte";

  let {
    title,
    help,
    children,
  }: { title: string; help?: Snippet; children?: Snippet } = $props();
</script>

<div class="setting">
  <div>
    <b>{title}</b>
    {#if help}<p>{@render help()}</p>{/if}
  </div>
  {@render children?.()}
</div>

<style>
  .setting {
    display: flex;
    gap: var(--space-4);
    align-items: center;
    justify-content: space-between;
    padding: var(--space-2) 0;
    border-top: 1px solid var(--color-border);
  }

  .setting:first-of-type {
    border-top: 0;
  }

  p {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  /* A dropdown keeps its width; without this a long help line squeezes it to nothing. */
  .setting :global(.dd) {
    flex: 0 0 12em;
  }

  .setting :global(code) {
    max-width: 50%;
    color: var(--color-text-muted);
    overflow-wrap: anywhere;
    text-align: right;
  }
</style>
