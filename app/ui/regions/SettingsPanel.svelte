<!-- The saved settings, read only, grouped as in Munder Difflin's Settings page. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";

  type Caps = { five_hour: number; daily: number; weekly: number; monthly: number };
  type View = {
    general: { vault: string | null; network: string };
    agents: { provider: string; model: string; ollama: string };
    budgets: { app: Caps; assistant: Caps; max_tool_calls: number };
    memory: { max_bytes: number };
  };

  let view = $state<View | null>(null);
  let failed = $state(false);

  onMount(async () => {
    try {
      view = await invoke<View>("sidecar_call", { method: "settings" });
    } catch (cause) {
      failed = true;
      console.error("Could not read the settings", cause);
    }
  });

  // A cap of 0 means no limit for that window.
  const cap = (n: number) => (n === 0 ? "no cap" : n.toLocaleString());

  let query = $state("");

  // Each section lists [label, value] rows; the filter keeps rows whose text matches.
  const sections = $derived.by(() => {
    if (!view) return [];
    const all = [
      { title: "General", rows: [["Vault", view.general.vault ?? "not set"], ["Network", view.general.network]] },
      {
        title: "Agents and models",
        rows: [["Provider", view.agents.provider], ["Model", view.agents.model], ["Ollama model", view.agents.ollama]],
      },
      {
        title: "Autonomy and budgets",
        rows: [
          ["Max tool calls per request", String(view.budgets.max_tool_calls)],
          ["App, 5 hours", cap(view.budgets.app.five_hour)],
          ["App, daily", cap(view.budgets.app.daily)],
          ["Assistant, daily", cap(view.budgets.assistant.daily)],
        ],
      },
      {
        title: "Memory and knowledge",
        rows: [["Note size before archiving", `${view.memory.max_bytes.toLocaleString()} bytes`]],
      },
    ];
    const q = query.trim().toLowerCase();
    return all
      .map((s) => ({ ...s, rows: s.rows.filter(([label, value]) => `${s.title} ${label} ${value}`.toLowerCase().includes(q)) }))
      .filter((s) => s.rows.length > 0);
  });
</script>

<section class="settings" aria-label="Settings">
  {#if failed}
    <p class="muted">Could not read the settings.</p>
  {:else if view}
    <input type="search" aria-label="Filter settings" placeholder="Filter settings" bind:value={query} />
    {#each sections as section (section.title)}
      <h3>{section.title}</h3>
      <dl>
        {#each section.rows as [label, value] (label)}
          <dt>{label}</dt><dd>{value}</dd>
        {/each}
      </dl>
    {:else}
      <p class="muted">No settings match "{query}".</p>
    {/each}

    <p class="muted">Voice, dictation and prerequisites are not built yet.</p>
  {/if}
</section>

<style>
  .settings {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  h3 {
    margin: var(--space-2) 0 var(--space-1);
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
    color: var(--color-md-accent);
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }

  dt {
    color: var(--color-md-text-muted);
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
