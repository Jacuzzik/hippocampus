<!-- The saved settings, read only: seven options on the left, the chosen one on the right. -->
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

  // Munder Difflin's seven settings options. Voice, Dictation and Prerequisites are not built yet.
  const OPTIONS = [
    "General",
    "Agents and models",
    "Autonomy and budgets",
    "Memory and knowledge",
    "Voice",
    "Dictation",
    "Prerequisites",
  ];

  let view = $state<View | null>(null);
  let failed = $state(false);
  let option = $state("General");

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

  // Rows for the chosen option, as [label, value] pairs.
  const rows = $derived.by((): [string, string][] => {
    if (!view) return [];
    switch (option) {
      case "General":
        return [["Vault", view.general.vault ?? "not set"], ["Network", view.general.network]];
      case "Agents and models":
        return [["Provider", view.agents.provider], ["Model", view.agents.model], ["Ollama model", view.agents.ollama]];
      case "Autonomy and budgets":
        return [
          ["Max tool calls per request", String(view.budgets.max_tool_calls)],
          ["App, 5 hours", cap(view.budgets.app.five_hour)],
          ["App, daily", cap(view.budgets.app.daily)],
          ["Assistant, daily", cap(view.budgets.assistant.daily)],
        ];
      case "Memory and knowledge":
        return [["Note size before archiving", `${view.memory.max_bytes.toLocaleString()} bytes`]];
      default:
        return [];
    }
  });
</script>

<section class="settings" aria-label="Settings">
  {#if failed}
    <p class="muted">Could not read the settings.</p>
  {:else if view}
    <div class="layout">
      <nav class="options" aria-label="Settings options">
        {#each OPTIONS as name (name)}
          <button type="button" aria-pressed={option === name} class:on={option === name} onclick={() => (option = name)}>
            {name}
          </button>
        {/each}
      </nav>
      <div class="detail">
        <h3>{option}</h3>
        {#if rows.length}
          <dl>
            {#each rows as [label, value] (label)}
              <dt>{label}</dt><dd>{value}</dd>
            {/each}
          </dl>
        {:else}
          <p class="muted">Not built yet.</p>
        {/if}
      </div>
    </div>
  {/if}
</section>

<style>
  .settings {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
  }

  .layout {
    display: grid;
    grid-template-columns: minmax(150px, 200px) 1fr;
    gap: var(--space-3);
    align-items: start;
  }

  .options {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .options button {
    min-height: 44px;
    padding: var(--space-1) var(--space-2);
    text-align: left;
    font-size: var(--font-size-xs);
    color: var(--color-md-text-muted);
    background: var(--color-md-surface);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .options button.on {
    color: var(--color-md-accent-on);
    background: var(--color-md-accent);
    border-color: var(--color-md-accent);
  }

  h3 {
    margin: 0 0 var(--space-2);
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
