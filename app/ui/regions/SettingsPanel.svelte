<!-- The saved settings, read only, laid out as the Control panel's stacked sections. -->
<script lang="ts">
  import "../control/control.css";
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
  let query = $state("");

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

  // Munder Difflin's seven settings sections. A section with no rows says it is not built yet.
  const sections = $derived.by((): { title: string; rows: [string, string][] }[] => {
    if (!view) return [];
    const all = [
      { title: "General", rows: [["Vault", view.general.vault ?? "not set"], ["Network", view.general.network]] as [string, string][] },
      {
        title: "Agents and models",
        rows: [["Provider", view.agents.provider], ["Model", view.agents.model], ["Ollama model", view.agents.ollama]] as [string, string][],
      },
      {
        title: "Autonomy and budgets",
        rows: [
          ["Max tool calls per request", String(view.budgets.max_tool_calls)],
          ["App, 5 hours", cap(view.budgets.app.five_hour)],
          ["App, daily", cap(view.budgets.app.daily)],
          ["Assistant, daily", cap(view.budgets.assistant.daily)],
        ] as [string, string][],
      },
      {
        title: "Memory and knowledge",
        rows: [["Note size before archiving", `${view.memory.max_bytes.toLocaleString()} bytes`]] as [string, string][],
      },
      { title: "Voice", rows: [] as [string, string][] },
      { title: "Dictation", rows: [] as [string, string][] },
      { title: "Prerequisites", rows: [] as [string, string][] },
    ];
    const q = query.trim().toLowerCase();
    return all.map((s) => ({
      title: s.title,
      rows: s.rows.filter(([label, value]) => `${s.title} ${label} ${value}`.toLowerCase().includes(q)),
    }));
  });
</script>

<section class="settings" aria-label="Settings">
  {#if failed}
    <p class="muted">Could not read the settings.</p>
  {:else if view}
    <input type="search" aria-label="Filter settings" placeholder="Filter settings" bind:value={query} />
    {#each sections as section (section.title)}
      {#if section.rows.length || !query.trim()}
        <section class="control-section" aria-label={section.title}>
          <h3>{section.title}</h3>
          {#if section.rows.length}
            <dl>
              {#each section.rows as [label, value] (label)}
                <dt>{label}</dt><dd>{value}</dd>
              {/each}
            </dl>
          {:else}
            <p class="hint">Not built yet.</p>
          {/if}
        </section>
      {/if}
    {:else}
      <p class="muted">No settings match "{query}".</p>
    {/each}
  {/if}
</section>

<style>
  .settings {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  input[type="search"] {
    width: 100%;
    box-sizing: border-box;
    margin-bottom: var(--space-2);
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
