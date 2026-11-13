<script lang="ts">
  // What a list shows while its first answer is on the way: grey bars in the shape of rows.
  // Shown only after a short wait, so a fast answer does not flash; screen readers hear "Loading".
  import { onMount } from "svelte";

  let { what, rows = 3 }: { what: string; rows?: number } = $props();
  let late = $state(false);
  onMount(() => {
    const timer = setTimeout(() => (late = true), 300);
    return () => clearTimeout(timer);
  });
</script>

<div class="loading" role="status" aria-busy="true" aria-label="Loading {what}">
  {#if late}
    {#each [...Array(rows).keys()] as i (i)}
      <span class="skeleton" style:width="{90 - i * 15}%"></span>
    {/each}
  {/if}
</div>

<style>
  .loading {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
  }
</style>
