<!-- The bottom agent row: the main agent first (fixed), then added agents that can be moved. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import logo from "../assets/brand/hippocampus-mark-purple.png";

  type Account = { claude: boolean; model: string };

  let account = $state<Account | null>(null);
  // Added agents only; the main agent is not in this list, so it cannot be moved.
  let added = $state<{ id: string; name: string }[]>([]);

  onMount(async () => {
    try {
      account = await invoke<Account>("sidecar_call", { method: "account" });
    } catch (cause) {
      console.error("Could not read the provider in use", cause);
    }
  });

  const provider = $derived(account ? (account.claude ? "Claude Code" : "Ollama") : "...");

  function move(index: number, step: number): void {
    const target = index + step;
    if (target < 0 || target >= added.length) return;
    const next = [...added];
    const moved = next[index];
    const other = next[target];
    if (!moved || !other) return;
    next[index] = other;
    next[target] = moved;
    added = next;
  }
</script>

<div class="agent-bar" aria-label="Agents">
  <div class="chip main">
    <img src={logo} alt="" />
    <div>
      <b>HIPPO</b>
      <i>{provider}</i>
      <small class="fixed">MAIN · FIXED</small>
    </div>
    <span class="tokens">— tokens</span>
  </div>
  {#each added as agent, index (agent.id)}
    <div class="chip">
      <img src={logo} alt="" />
      <div>
        <b>{agent.name}</b>
        <i>{provider}</i>
      </div>
      <span class="tokens">— tokens</span>
      <button type="button" aria-label="Move {agent.name} left" onclick={() => move(index, -1)}>‹</button>
      <button type="button" aria-label="Move {agent.name} right" onclick={() => move(index, 1)}>›</button>
    </div>
  {/each}
  <!-- Adding agents is not built yet; the button is shown so the layout matches the mockup. -->
  <button type="button" class="add" disabled title="Adding agents is not built yet">+ Add agent</button>
</div>

<style>
  .agent-bar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
    overflow-x: auto;
  }

  .chip {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex: none;
    min-height: 64px;
    min-width: 180px;
    padding: var(--space-2) var(--space-3);
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    border-radius: var(--radius-md);
    box-shadow: 2px 2px 0 var(--color-md-shadow);
    white-space: nowrap;
  }

  .chip img {
    width: 40px;
    height: 40px;
    object-fit: contain;
    flex: none;
  }

  .chip b {
    display: block;
    font-size: var(--font-size-xs);
  }

  .chip i {
    font-style: normal;
    font-size: 10px;
    color: var(--color-md-card-text);
    opacity: 0.7;
  }

  .fixed {
    display: block;
    font-family: "Press Start 2P", monospace;
    font-size: 6px;
    color: var(--color-accent);
  }

  .add {
    flex: none;
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 1px dashed var(--color-border);
    border-radius: var(--radius-md);
    background: none;
    color: var(--color-text-muted);
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
    cursor: default;
  }

  .tokens {
    font-family: var(--font-mono);
    font-size: 10px;
  }

  .chip button {
    padding: 0 var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text);
    cursor: pointer;
  }
</style>
