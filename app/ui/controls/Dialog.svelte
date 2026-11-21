<script lang="ts">
  // 3.08 The one dialog frame: backdrop, box, title, keyboard focus and Escape. A click outside, or Escape, calls onclose.
  // Escape stops here so the graph's own Escape (which clears the selection) does not also run.
  import type { Snippet } from "svelte";
  import { dialogFocus } from "./dialogFocus.ts";

  let {
    title,
    onclose,
    children,
  }: { title: string; onclose: () => void; children: Snippet } = $props();

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }
</script>

<div class="scrim" role="presentation" onmousedown={onclose}>
  <div
    class="box"
    role="dialog"
    aria-modal="true"
    aria-label={title}
    tabindex="-1"
    use:dialogFocus
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    <h2>{title}</h2>
    {@render children()}
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 10;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding-top: 12vh;
  }

  .box {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    width: min(560px, 90vw);
    padding: var(--space-4);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    border-radius: var(--radius-sm);
    color: var(--color-text);
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-sm);
  }
</style>
