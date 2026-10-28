<!-- The owner's view: cards the main agent fills (numbers, analytics, anything for the owner). -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import AgentCard from "../assistant/AgentCard.svelte";
  import AgentStatus from "./AgentStatus.svelte";
  import logo from "../assets/brand/hippocampus-logo.png";

  let account = $state<{ claude: boolean; model: string } | null>(null);
  let showAgents = $state(false);

  onMount(async () => {
    try {
      account = await invoke<{ claude: boolean; model: string }>("sidecar_call", {
        method: "account",
      });
    } catch (cause) {
      console.error("Could not read the model in use", cause);
    }
  });
</script>

<section class="owner-panel md-theme" aria-label="Owner panel">
  <div class="card-row">
    <AgentCard
      name="HIPPO"
      accent="accent"
      logo={logo}
      model={account?.model ?? "Loading model"}
      details={account
        ? [
            account.claude
              ? "Replies with your Claude key"
              : "No Claude key: local Ollama",
          ]
        : []}
    />
    <button
      class="agents-btn"
      type="button"
      aria-expanded={showAgents}
      onclick={() => (showAgents = !showAgents)}>Agents</button
    >
  </div>
  {#if showAgents}
    <AgentStatus />
  {/if}
  <p class="empty">No cards yet.</p>
</section>

<style>
  .owner-panel {
    display: flex;
    flex-direction: column;
    height: 35%;
    min-height: 8rem;
    padding: var(--space-3);
    border-top: 1px solid var(--color-border);
    overflow: auto;
  }

  .empty {
    margin: auto;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }
</style>
