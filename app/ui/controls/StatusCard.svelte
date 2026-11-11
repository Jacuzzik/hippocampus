<script lang="ts" module>
  export type CardStatus = "Connected" | "Local only" | "Not connected" | "Needs attention" | "Planned";
</script>

<script lang="ts">
  import type { Snippet } from "svelte";

  // One card for anything that can be on, off or not built yet: a connector, a feature, a check.
  // A feature that is not ready still gets a card that says what it will do and what is missing.
  let {
    name,
    what,
    status,
    reason = "",
    children,
  }: { name: string; what: string; status: CardStatus; reason?: string; children?: Snippet } = $props();
  const tone = $derived(
    status === "Connected" || status === "Local only" ? "ok" : status === "Needs attention" ? "bad" : status === "Planned" ? "plan" : "off",
  );
</script>

<article class="card">
  <header>
    <b>{name}</b>
    <span class="chip {tone}">{status}</span>
  </header>
  <p>{what}</p>
  {#if reason}<p class="reason">{reason}</p>{/if}
  {#if children}<div class="actions">{@render children()}</div>{/if}
</article>

<style>
  .card {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 0;
    padding: var(--space-3);
    font-size: var(--font-size-sm);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  header {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    justify-content: space-between;
  }

  p {
    margin: 0;
    color: var(--color-text-muted);
  }

  .reason {
    color: var(--color-text-subtle);
    font-size: var(--font-size-xs);
  }

  .chip {
    flex: none;
    padding: 0 var(--space-2);
    font-size: var(--font-size-tag);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid currentColor;
    border-radius: var(--radius-sm);
  }

  .chip.ok {
    color: var(--color-success);
  }

  .chip.bad {
    color: var(--color-danger);
  }

  .chip.plan {
    color: var(--color-think);
  }

  .chip.off {
    color: var(--color-text-muted);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-1);
  }
</style>
