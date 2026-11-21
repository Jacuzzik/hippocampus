<script lang="ts">
  // 3.08 The one dialog frame: backdrop, box, title, keyboard focus and Escape. A click outside, or Escape, calls onclose.
  // Escape stops here so the graph's own Escape (which clears the selection) does not also run.
  import type { Snippet } from "svelte";
  import { dialogFocus } from "./dialogFocus.ts";

  let {
    title,
    onclose,
    children,
    heading,
    header,
    closeLabel,
    bare = false,
    center = false,
    dim = false,
    z = 10,
    width = "min(560px, 90vw)",
    height,
  }: {
    /** The accessible name; also the visible heading unless `heading` or `header` says otherwise. */
    title: string;
    onclose: () => void;
    children: Snippet;
    /** Visible heading when it should differ from the accessible name. */
    heading?: string;
    /** Replaces the whole heading row (for a dialog with a search box or other controls in it). */
    header?: Snippet;
    /** Adds a close button in the heading row with this accessible name. */
    closeLabel?: string;
    /** No heading row at all: the content brings its own (the command box). */
    bare?: boolean;
    /** Centre the box on the screen instead of near the top. */
    center?: boolean;
    /** Darken the page behind the box. */
    dim?: boolean;
    z?: number;
    width?: string;
    height?: string;
  } = $props();

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }
</script>

<div
  class="scrim"
  class:center
  class:dim
  style:z-index={z}
  role="presentation"
  onmousedown={onclose}
>
  <div
    class="box"
    role="dialog"
    aria-modal="true"
    aria-label={title}
    tabindex="-1"
    style:width
    style:height
    use:dialogFocus
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    {#if header}
      {@render header()}
    {:else if !bare}
      <header>
        <h2>{heading ?? title}</h2>
        {#if closeLabel}
          <button
            type="button"
            class="close"
            aria-label={closeLabel}
            onclick={onclose}>×</button
          >
        {/if}
      </header>
    {/if}
    {@render children()}
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding-top: 12vh;
  }

  .scrim.center {
    align-items: center;
    padding-top: 0;
  }

  .scrim.dim {
    background: color-mix(in srgb, var(--color-bg-0) 70%, transparent);
  }

  .box {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    box-sizing: border-box;
    max-width: calc(100vw - 2 * var(--space-4));
    max-height: calc(100vh - 2 * var(--space-4));
    overflow-y: auto;
    padding: var(--space-4);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    border-radius: var(--radius-sm);
    color: var(--color-text);
  }

  header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-sm);
  }

  .close {
    width: var(--size-28);
    height: var(--size-28);
    margin-left: auto;
    line-height: 1;
    color: var(--color-text-muted);
    font-size: var(--font-size-xl);
    background: none;
    border: none;
    cursor: pointer;
  }
</style>
