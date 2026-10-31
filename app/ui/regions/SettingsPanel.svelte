<!-- Settings laid out like Munder Difflin's: nine categories on the left, each with its option labels. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";

  type View = {
    general: { vault: string | null; network: string };
    agents: { provider: string; model: string; ollama: string };
    budgets: { max_tool_calls: number };
    memory: { max_bytes: number };
  };
  type Group = { heading?: string; items: string[] };
  type Category = { name: string; groups: Group[] };

  // Munder Difflin's nine settings categories and their option labels, in its order.
  const CATEGORIES: Category[] = [
    {
      name: "General",
      groups: [
        { items: ["Home folder", "Skip the config picker on launch", "Environment", "Keep Mac awake while agents run", "Keep my agent order", "Sidebar shows only agents and notes", "Explain things simply", "Default view", "Theme", "Arabic / RTL text in terminals", "Language"] },
        { heading: "Notifications", items: ["Desktop notifications"] },
        { heading: "Maintenance", items: ["Scheduled auto-compact", "Auto-update", "Anonymous usage stats"] },
        { heading: "DANGER ZONE", items: ["Reset & start over"] },
      ],
    },
    {
      name: "Prerequisites",
      groups: [{ items: ["Prerequisites", "Memory layer", "Agent engines"] }],
    },
    {
      name: "Agents & Models",
      groups: [{ items: ["Default agent model", "Advanced", "Max turns per run"] }],
    },
    {
      name: "Autonomy & Budgets",
      groups: [
        { heading: "Autonomy", items: ["Autonomous — agents act without asking", "Ask-first — agents pause for tool approval"] },
        { heading: "Circuit breaker", items: ["token velocity (tok/min)", "repeated-tool limit", "error-storm limit", "Hard stop", "kill on trip", "steer first"] },
        { heading: "Archiving", items: ["Ticket key prefix", "archive done tasks after (days)", "flag untouched tasks after (days)", "archive untouched tasks after (days)", "remind about an open question after (days)", "condense the board past (tokens)"] },
      ],
    },
    {
      name: "Connections",
      groups: [
        { heading: "Slack", items: ["Slack integration", "Signing secret", "Bot token", "Channel id (optional)", "Port", "Proactive posting (app-initiated) — off by default"] },
        { heading: "Webhook triggers", items: ["Mode", "Secret", "URL"] },
      ],
    },
    {
      name: "Orchestrator's voice",
      groups: [{ items: ["Groq API key", "Model", "OpenAI API key · voice", "Idle auto-disconnect"] }],
    },
    {
      name: "Dictation & Meetings",
      groups: [
        { items: ["Engine", "Whisper model", "Dictate into any app", "Push to talk key", "Start and stop sounds", "Built in vocabulary", "Your words", "Test paste"] },
        { heading: "Meetings", items: ["Start or stop a meeting", "Also record the other side of calls", "Take screenshots into the Stapler"] },
        { heading: "Permissions", items: ["Microphone", "Accessibility"] },
      ],
    },
    {
      name: "Memory & Knowledge",
      groups: [{ items: ["Search across memory", "Cross-session recall", "Knowledge Graph", "Enterprise knowledge base", "Memory folder", "Show in folder"] }],
    },
    {
      name: "Keys & Secrets",
      groups: [{ items: ["AI engine providers (BYOK)", "API keys"] }],
    },
  ];

  let view = $state<View | null>(null);
  let failed = $state(false);
  let category = $state("General");

  onMount(async () => {
    try {
      view = await invoke<View>("sidecar_call", { method: "settings" });
    } catch (cause) {
      failed = true;
      console.error("Could not read the settings", cause);
    }
  });

  // Values read from the saved settings, keyed by option label. Any other row says "Not in Hippocampus yet".
  const valueOf = $derived.by((): Record<string, string> => {
    if (!view) return {};
    return {
      "Home folder": view.general.vault ?? "not set",
      "Default agent model": `${view.agents.provider} · ${view.agents.model}`,
      "AI engine providers (BYOK)": view.agents.provider,
      "Agent engines": `Ollama fallback · ${view.agents.ollama}`,
      "Max turns per run": `${view.budgets.max_tool_calls} tool calls per request`,
    };
  });

  const current = $derived<Category>(CATEGORIES.find((c) => c.name === category) ?? { name: category, groups: [] });
</script>

<section class="settings" aria-label="Settings">
  {#if failed}
    <p class="muted">Could not read the settings.</p>
  {:else if view}
    <div class="layout">
      <nav class="options" aria-label="Settings categories">
        {#each CATEGORIES as item (item.name)}
          <button type="button" aria-pressed={category === item.name} class:on={category === item.name} onclick={() => (category = item.name)}>
            {item.name}
          </button>
        {/each}
      </nav>
      <div class="detail">
        <h3>{current.name}</h3>
        {#each current.groups as group (group.heading ?? "")}
          {#if group.heading}<h4>{group.heading}</h4>{/if}
          <dl>
            {#each group.items as label (label)}
              <dt>{label}</dt>
              {#if valueOf[label]}
                <dd>{valueOf[label]}</dd>
              {:else}
                <dd class="missing">Not in Hippocampus yet</dd>
              {/if}
            {/each}
          </dl>
        {/each}
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

  h4 {
    margin: var(--space-2) 0 var(--space-1);
    font-size: var(--font-size-xs);
    color: var(--color-md-text-muted);
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }

  dt {
    color: var(--color-md-text);
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
    color: var(--color-md-text-muted);
  }

  dd.missing {
    font-style: italic;
  }
</style>
