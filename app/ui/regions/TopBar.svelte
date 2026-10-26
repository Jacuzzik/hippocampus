<script lang="ts">
  import Orb from "../assistant/Orb.svelte";
  import { assistant } from "../assistant/session.svelte";
</script>

<header class="top-bar" aria-label="Top bar">
  <span class="brand">Hippocampus</span>
  <span class="orb-slot"><Orb state={assistant.chat.orb} /></span>
</header>

<style>
  .top-bar {
    grid-area: top;
    display: flex;
    align-items: center;
    padding: 0 var(--space-4);
    background: var(--color-bg-1);
    border-bottom: 1px solid var(--color-border);
  }

  /* Obsidian's tab-header title: small and semibold, not a logotype. */
  .brand {
    font-size: var(--font-size-sm);
    font-weight: 600;
  }

  .orb-slot {
    margin-left: auto;
  }
</style>
