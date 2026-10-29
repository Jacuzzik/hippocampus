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
</script>

<section class="settings" aria-label="Settings">
  {#if failed}
    <p class="muted">Could not read the settings.</p>
  {:else if view}
    <h3>General</h3>
    <dl>
      <dt>Vault</dt><dd>{view.general.vault ?? "not set"}</dd>
      <dt>Network</dt><dd>{view.general.network}</dd>
    </dl>

    <h3>Agents and models</h3>
    <dl>
      <dt>Provider</dt><dd>{view.agents.provider}</dd>
      <dt>Model</dt><dd>{view.agents.model}</dd>
      <dt>Ollama model</dt><dd>{view.agents.ollama}</dd>
    </dl>

    <h3>Autonomy and budgets</h3>
    <dl>
      <dt>Max tool calls per request</dt><dd>{view.budgets.max_tool_calls}</dd>
      <dt>App, 5 hours</dt><dd>{cap(view.budgets.app.five_hour)}</dd>
      <dt>App, daily</dt><dd>{cap(view.budgets.app.daily)}</dd>
      <dt>Assistant, daily</dt><dd>{cap(view.budgets.assistant.daily)}</dd>
    </dl>

    <h3>Memory and knowledge</h3>
    <dl>
      <dt>Note size before archiving</dt><dd>{view.memory.max_bytes.toLocaleString()} bytes</dd>
    </dl>

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
