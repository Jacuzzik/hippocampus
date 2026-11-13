<script lang="ts">
  // The one button. Four looks and two sizes, all from tokens; the rest (type, disabled, aria-*, onclick)
  // passes straight through, so a button keeps the name and behaviour its tests already know.
  import type { Snippet } from "svelte";
  import type { HTMLButtonAttributes } from "svelte/elements";

  let {
    variant = "secondary",
    size = "md",
    children,
    ...rest
  }: {
    variant?: "primary" | "secondary" | "danger" | "ghost";
    size?: "sm" | "md";
    children: Snippet;
  } & HTMLButtonAttributes = $props();
</script>

<button type="button" class="btn {variant} {size}" {...rest}
  >{@render children()}</button
>

<style>
  .btn {
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .md {
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-sm);
  }

  .sm {
    padding: var(--space-1) var(--space-2);
    font-size: var(--font-size-xs);
  }

  .btn:hover:not(:disabled) {
    border-color: var(--color-text-subtle);
  }

  .btn:disabled {
    color: var(--color-text-subtle);
    cursor: default;
  }

  .primary {
    color: var(--color-accent-on);
    background: var(--color-accent);
    border-color: var(--color-accent);
  }

  .primary:disabled {
    color: var(--color-accent-on);
    opacity: 0.5;
  }

  .primary:hover:not(:disabled) {
    border-color: var(--color-accent);
    filter: brightness(1.1);
  }

  .danger {
    color: var(--color-danger);
    border-color: var(--color-danger);
  }

  .danger:hover:not(:disabled) {
    border-color: var(--color-danger);
    background: var(--color-bg-1);
  }

  .ghost {
    background: transparent;
    border-color: transparent;
    color: var(--color-text-muted);
  }

  .ghost:hover:not(:disabled) {
    border-color: var(--color-border);
  }
</style>
