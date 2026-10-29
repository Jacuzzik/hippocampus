<script lang="ts">
  import { ORB_LABELS } from "../assistant/model";
  import { assistant } from "../assistant/session.svelte";
  import AgentBar from "../owner/AgentBar.svelte";
  import type { GraphData } from "../graph/model.ts";

  let { data = null }: { data?: GraphData | null } = $props();

  const links = $derived(data?.edges.length ?? 0);
</script>

<footer class="status-bar md-theme">
  <AgentBar />
  <span class="counts">
    <span>{data?.nodes.length ?? 0} notes</span>
    <span>{links} links</span>
    <span class="assistant-state">{ORB_LABELS[assistant.chat.orb]}</span>
  </span>
</footer>

<style>
  .status-bar {
    grid-area: status;
    display: flex;
    align-items: center;
    gap: var(--space-4);
    height: var(--layout-status-bar-height);
    padding: 0 var(--space-3);
    background: var(--color-bg-1);
    border-top: 1px solid var(--color-border);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    white-space: nowrap;
  }

  .counts {
    display: flex;
    gap: var(--space-3);
    margin-left: auto;
    flex: none;
  }
</style>
