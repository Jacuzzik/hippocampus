<script lang="ts">
  import type { Snippet } from "svelte";
  import { errorText, recordError } from "../crashLog.svelte.ts";

  // Wraps one region of the app. If that region throws while drawing, only it is replaced
  // by this notice; the rest of the window keeps working. "Reload panel" draws it again.
  let { name, area = "", children }: { name: string; area?: string; children: Snippet } = $props();
</script>

<svelte:boundary onerror={(cause) => recordError(name, cause)}>
  {@render children()}
  {#snippet failed(cause, reset)}
    <div class="failed" role="alert" style:grid-area={area || null}>
      <b>{name} hit an error</b>
      <p>{errorText(cause)}</p>
      <button type="button" onclick={reset}>Reload panel</button>
    </div>
  {/snippet}
</svelte:boundary>

<style>
  .failed {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    align-items: flex-start;
    min-width: 0;
    margin: var(--space-2);
    padding: var(--space-3);
    color: var(--color-text);
    font-family: var(--font-ui);
    font-size: var(--font-size-sm);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-danger);
    border-radius: var(--radius-sm);
  }

  p {
    margin: 0;
    color: var(--color-text-muted);
    overflow-wrap: anywhere;
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
