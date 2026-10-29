<!-- The saved settings, read only. Seven options, as in Munder Difflin's Settings page. -->
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

  // The seven options from Munder Difflin's Settings page. Only the first four have saved values so far.
  const OPTIONS = [
    { id: "general", label: "General" },
    { id: "agents", label: "Agents and models" },
    { id: "autonomy", label: "Autonomy and budgets" },
    { id: "memory", label: "Memory and knowledge" },
    { id: "voice", label: "Voice" },
    { id: "dictation", label: "Dictation" },
    { id: "prerequisites", label: "Prerequisites" },
  ];

  let view = $state<View | null>(null);
  let failed = $state(false);
  let option = $state("general");
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

  // Rows for the chosen option as [label, value] pairs, narrowed by the filter.
  const rows = $derived.by((): [string, string][] => {
    if (!view) return [];
    const byOption: Record<string, [string, string][]> = {
      general: [["Vault", view.general.vault ?? "not set"], ["Network", view.general.network]],
      agents: [["Provider", view.agents.provider], ["Model", view.agents.model], ["Ollama model", view.agents.ollama]],
      autonomy: [
        ["Max tool calls per request", String(view.budgets.max_tool_calls)],
        ["App, 5 hours", cap(view.budgets.app.five_hour)],
        ["App, daily", cap(view.budgets.app.daily)],
        ["Assistant, daily", cap(view.budgets.assistant.daily)],
      ],
      memory: [["Note size before archiving", `${view.memory.max_bytes.toLocaleString()} bytes`]],
    };
    const q = query.trim().toLowerCase();
    return (byOption[option] ?? []).filter(([label, value]) => `${label} ${value}`.toLowerCase().includes(q));
  });
</script>

<section class="settings" aria-label="Settings">
  {#if failed}
    <p class="muted">Could not read the settings.</p>
  {:else if view}
    <nav class="options" aria-label="Settings options">
      {#each OPTIONS as item (item.id)}
        <button
          type="button"
          class:on={option === item.id}
          aria-pressed={option === item.id}
          onclick={() => (option = item.id)}>{item.label}</button
        >
      {/each}
    </nav>

    {#if ["voice", "dictation", "prerequisites"].includes(option)}
      <p class="muted">Not built yet.</p>
    {:else}
      <input type="search" aria-label="Filter settings" placeholder="Filter settings" bind:value={query} />
      {#if rows.length}
        <dl>
          {#each rows as [label, value] (label)}
            <dt>{label}</dt><dd>{value}</dd>
          {/each}
        </dl>
      {:else}
        <p class="muted">No settings match "{query}".</p>
      {/if}
    {/if}
  {/if}
</section>

<style>
  .settings {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  .options {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: var(--space-1);
    margin-bottom: var(--space-2);
  }

  .options button {
    min-height: 44px;
    padding: var(--space-1);
    font-family: "Press Start 2P", monospace;
    font-size: 7px;
    text-transform: uppercase;
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text-muted);
    cursor: pointer;
  }

  .options button.on {
    background: var(--color-md-accent);
    color: var(--color-md-accent-on);
    border-color: var(--color-md-accent);
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
