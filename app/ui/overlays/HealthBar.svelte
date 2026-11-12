<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { crashLog } from "../crashLog.svelte.ts";
  import { systemWarnings, type SystemStats } from "../health.ts";
  import { every } from "../poll.ts";

  // A thin strip that says when something is wrong: the backend is not answering, the disk or
  // memory is almost full, or the UI recorded errors since this window opened. Hidden when all is well.
  let { backendDown = false }: { backendDown?: boolean } = $props();
  let open = $state(false);
  const recent = $derived(crashLog.rows.slice(-5).reverse());

  // Disk and memory are checked four times a minute; a failed read keeps the last answer.
  let stats = $state<SystemStats | null>(null);
  const warnings = $derived(systemWarnings(stats));
  onMount(() => {
    const read = (): void => {
      invoke<SystemStats>("sidecar_call", { method: "system" }).then(
        (value) => (stats = value),
        () => {},
      );
    };
    read();
    return every(read, 15000);
  });
</script>

{#if backendDown || warnings.length > 0 || crashLog.fresh > 0}
  <div class="health" role="status">
    {#if backendDown}
      <span class="item"
        ><span class="dot down" aria-hidden="true"></span>Backend not answering.
        Retrying…</span
      >
    {/if}
    {#each warnings as line (line)}
      <span class="item"
        ><span class="dot down" aria-hidden="true"></span>{line}</span
      >
    {/each}
    {#if crashLog.fresh > 0}
      <span class="item">
        <span class="dot" aria-hidden="true"></span>
        {crashLog.fresh} UI {crashLog.fresh === 1 ? "error" : "errors"} recorded
        <button
          type="button"
          aria-expanded={open}
          onclick={() => (open = !open)}>{open ? "Hide" : "Details"}</button
        >
        <button
          type="button"
          onclick={() => ((open = false), crashLog.dismiss())}>Dismiss</button
        >
      </span>
    {/if}
    {#if open && crashLog.fresh > 0}
      <ul>
        {#each recent as row (row.at + row.message)}
          <li><b>{row.source}</b> {row.message}</li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<style>
  .health {
    position: fixed;
    top: var(--space-2);
    left: 50%;
    z-index: 30;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-4);
    align-items: center;
    max-width: min(720px, calc(100vw - 2 * var(--space-4)));
    padding: var(--space-1) var(--space-3);
    color: var(--color-text);
    font-family: var(--font-ui);
    font-size: var(--font-size-sm);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-danger);
    border-radius: var(--radius-sm);
    box-shadow: var(--layout-drawer-shadow);
    transform: translateX(-50%);
  }

  .item {
    display: inline-flex;
    gap: var(--space-2);
    align-items: center;
  }

  .dot {
    width: 8px;
    height: 8px;
    background: var(--color-pending);
    border-radius: 50%;
  }

  .dot.down {
    background: var(--color-danger);
  }

  button {
    padding: 0 var(--space-2);
    color: var(--color-text-muted);
    font: inherit;
    background: none;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  ul {
    flex-basis: 100%;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    color: var(--color-text-muted);
    overflow-wrap: anywhere;
  }
</style>
