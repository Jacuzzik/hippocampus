<!-- The brain graph in numbers: note and link counts, and the most linked notes. Read only. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";

  type GraphNode = { id: string; title: string; memory: boolean };
  type GraphData = { nodes: GraphNode[]; edges: [string, string][] };

  let graph = $state<GraphData | null>(null);
  let failed = $state(false);

  onMount(async () => {
    try {
      graph = await invoke<GraphData>("sidecar_call", { method: "graph" });
    } catch (cause) {
      failed = true;
      console.error("Could not read the brain graph", cause);
    }
  });

  const linked = $derived.by(() => {
    if (!graph) return [];
    const count = new Map<string, number>();
    for (const [from, to] of graph.edges) {
      count.set(from, (count.get(from) ?? 0) + 1);
      count.set(to, (count.get(to) ?? 0) + 1);
    }
    return graph.nodes
      .map((node) => ({ ...node, links: count.get(node.id) ?? 0 }))
      .filter((node) => node.links > 0)
      .sort((a, b) => b.links - a.links)
      .slice(0, 8);
  });
</script>

<section class="graph" aria-label="Graph">
  {#if failed}
    <p class="muted">Open a brain folder to see its graph.</p>
  {:else if !graph}
    <p class="muted">Loading…</p>
  {:else if graph.nodes.length === 0}
    <p class="muted">No notes in this brain yet.</p>
  {:else}
    <dl>
      <dt>Notes</dt>
      <dd>{graph.nodes.length}</dd>
      <dt>Links</dt>
      <dd>{graph.edges.length}</dd>
      <dt>Memory notes</dt>
      <dd>{graph.nodes.filter((node) => node.memory).length}</dd>
    </dl>
    <h3>Most linked</h3>
    {#if linked.length === 0}
      <p class="muted">No links between notes yet.</p>
    {:else}
      <ul>
        {#each linked as node (node.id)}
          <li>
            <span>{node.title}</span>
            <small>{node.links} {node.links === 1 ? "link" : "links"}</small>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>

<style>
  .graph {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: var(--space-1) var(--space-2);
    margin: 0;
  }

  dt {
    color: var(--color-md-text-muted);
  }

  dd {
    margin: 0;
  }

  h3 {
    margin: var(--space-2) 0 var(--space-1);
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
    color: var(--color-md-accent);
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    gap: var(--space-2);
    align-items: baseline;
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--color-border);
  }

  li small {
    margin-left: auto;
    color: var(--color-md-text-muted);
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
