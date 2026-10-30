<!-- The bottom agent row: the main agent first (fixed), then added agents that can be moved. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import logo from "../assets/brand/hippocampus-mark-purple.png";
  import {
    addedAgents,
    archived,
    setAddedAgents,
    setArchived,
  } from "./addedAgents.svelte";
  import { AGENT_PROVIDERS, AVATARS } from "../control/model";
  import { ORB_LABELS } from "../assistant/model";
  import { assistant } from "../assistant/session.svelte";

  type Account = { claude: boolean; model: string };

  let account = $state<Account | null>(null);
  // Added agents only, minus archived ones; the main agent is not in this list, so it cannot be moved.
  const added = $derived(
    addedAgents.list.filter((a) => !archived.ids.includes(a.id)),
  );
  // The card whose options menu is open; null when closed. The bar sits at the bottom of the window, so the menu opens upward.
  let menu = $state<{ id: string; x: number; bottom: number } | null>(null);

  function openMenu(e: MouseEvent, id: string): void {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    menu = { id, x: rect.left, bottom: window.innerHeight - rect.top + 4 };
  }

  // Opens the Add agent dialog (identity, workspace, engine, briefing).
  let { onadd }: { onadd: () => void } = $props();

  onMount(async () => {
    try {
      account = await invoke<Account>("sidecar_call", { method: "account" });
    } catch (cause) {
      console.error("Could not read the provider in use", cause);
    }
  });

  const provider = $derived(
    account ? (account.claude ? "Claude Code" : "Ollama") : "...",
  );
  const labelOf = (id: string): string =>
    AGENT_PROVIDERS.find((p) => p.id === id)?.label ?? id;

  // The card whose INFO panel is open; null when closed. "—" marks a row the app has no data for yet.
  let info = $state<{
    name: string;
    role: string;
    provider: string;
    model: string;
    folder: string;
    face: string;
    boss: string;
    status: string;
    ctx: string;
  } | null>(null);
  const NO_DATA = "—";
  // An added agent keeps its character id; show the avatar's name.
  const faceOf = (id: string): string =>
    AVATARS.find((a) => a.id === id)?.name ?? NO_DATA;

  // Swaps a card with its visible neighbour in the full list, so archived cards keep their place.
  function move(id: string, step: number): void {
    const visible = added.map((a) => a.id);
    const target = visible[visible.indexOf(id) + step];
    if (target === undefined) return;
    const next = [...addedAgents.list];
    const i = next.findIndex((a) => a.id === id);
    const j = next.findIndex((a) => a.id === target);
    const a = next[i];
    const b = next[j];
    if (!a || !b) return;
    next[i] = b;
    next[j] = a;
    setAddedAgents(next);
  }
</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key !== "Escape") return;
    info = null;
    menu = null;
  }}
/>

{#snippet details(model: string, status: string)}
  <span class="line model">{model}</span>
  <span class="line command">Command · {NO_DATA}</span>
  <span class="line ctx" aria-label="Context {NO_DATA}">
    <span class="dashes" aria-hidden="true">----------</span> {NO_DATA}
  </span>
  <span class="line status">{status}</span>
{/snippet}

{#if menu}
  {@const open = menu}
  <div class="menu-scrim" role="presentation" onmousedown={() => (menu = null)}></div>
  <div
    class="card-menu"
    role="menu"
    style="left: {open.x}px; bottom: {open.bottom}px"
  >
    <button
      type="button"
      role="menuitem"
      onclick={() => {
        setArchived(open.id, true);
        menu = null;
      }}>Archive</button
    >
  </div>
{/if}

{#if info}
  <div class="info-scrim" role="presentation" onmousedown={() => (info = null)}>
    <div
      class="info-box"
      role="dialog"
      aria-modal="true"
      aria-label="{info.name} details"
      tabindex="-1"
      onmousedown={(e) => e.stopPropagation()}
    >
      <header>
        <b>{info.name}</b>
        <button
          type="button"
          class="info-close"
          aria-label="Close info"
          onclick={() => (info = null)}>×</button
        >
      </header>
      <dl>
        <dt>ROLE</dt>
        <dd>{info.role}</dd>
        <dt>PROVIDER</dt>
        <dd>{info.provider}</dd>
        <dt>MODEL</dt>
        <dd>{info.model}</dd>
        {#if info.folder}
          <dt>FOLDER</dt>
          <dd>{info.folder}</dd>
        {/if}
        <dt>FACE</dt>
        <dd>{info.face}</dd>
        <dt>BOSS</dt>
        <dd>{info.boss}</dd>
        <dt>STATUS</dt>
        <dd>{info.status}</dd>
        <dt>CTX</dt>
        <dd>{info.ctx}</dd>
      </dl>
    </div>
  </div>
{/if}

<div class="agent-bar" aria-label="Agents">
  <div class="chip main">
    <img src={logo} alt="" />
    <div class="text">
      <b>HIPPO</b>
      <i>{provider}</i>
      <small class="fixed">MAIN · FIXED</small>
      {@render details(account?.model ?? NO_DATA, ORB_LABELS[assistant.chat.orb])}
    </div>
    <span class="tokens">— tokens</span>
    <button type="button" class="ptt" disabled title="Push to talk is not set up yet"
      >PTT</button
    >
    <button
      type="button"
      class="info"
      aria-label="Info"
      onclick={() =>
        (info = {
          name: "HIPPO",
          role: "Main · fixed",
          provider,
          model: account?.model ?? "Loading model",
          folder: "",
          face: NO_DATA,
          boss: NO_DATA,
          status: ORB_LABELS[assistant.chat.orb],
          ctx: NO_DATA,
        })}>INFO</button
    >
  </div>
  {#each added as agent (agent.id)}
    <div class="chip">
      <button
        type="button"
        class="card-open"
        aria-haspopup="menu"
        aria-label="{agent.name} options"
        onclick={(e) => openMenu(e, agent.id)}
      >
        <img src={logo} alt="" />
        <span class="text">
          <b>{agent.name}</b>
          <i>{labelOf(agent.provider)}</i>
          {@render details(agent.model || NO_DATA, NO_DATA)}
        </span>
      </button>
      <span class="tokens">— tokens</span>
      <button
        type="button"
        class="ptt"
        disabled
        title="Push to talk is not set up yet">PTT</button
      >
      <button
        type="button"
        aria-label="Move {agent.name} left"
        onclick={() => move(agent.id, -1)}>‹</button
      >
      <button
        type="button"
        aria-label="Move {agent.name} right"
        onclick={() => move(agent.id, 1)}>›</button
      >
      <button
        type="button"
        class="info"
        aria-label="Info"
        onclick={() =>
          (info = {
            name: agent.name,
            role: "Added",
            provider: labelOf(agent.provider),
            model: agent.model,
            folder: agent.folder,
            face: faceOf(agent.character),
            boss: NO_DATA,
            status: NO_DATA,
            ctx: NO_DATA,
          })}>INFO</button
      >
    </div>
  {/each}
  <button type="button" class="add" onclick={onadd}>+ Add agent</button>
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
    cursor: pointer;
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

  .chip .info {
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
  }

  .info-scrim {
    position: fixed;
    inset: 0;
    z-index: 30;
    display: grid;
    place-items: center;
    background: rgb(0 0 0 / 0.5);
  }

  .info-box {
    width: min(340px, calc(100vw - 32px));
    padding: var(--space-4);
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    border: 2px solid var(--color-accent);
    border-radius: var(--radius-md);
  }

  .info-box header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .info-close {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--color-md-card-muted);
    font-size: 18px;
    cursor: pointer;
  }

  .info-box dl {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: var(--space-1) var(--space-2);
    margin: 0;
    font-size: var(--font-size-xs);
  }

  .info-box dt {
    color: var(--color-md-card-muted);
    font-size: 10px;
  }

  .info-box dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  /* .chip .card-open beats the generic .chip button rule. */
  .chip .card-open {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 0;
    border: none;
    background: none;
    color: inherit;
    text-align: left;
    cursor: pointer;
  }

  .text {
    display: block;
  }

  .line {
    display: block;
    font-size: 10px;
    opacity: 0.8;
  }

  .dashes {
    letter-spacing: 1px;
    opacity: 0.5;
  }

  .ptt {
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
  }

  .ptt:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .menu-scrim {
    position: fixed;
    inset: 0;
    z-index: 20;
  }

  .card-menu {
    position: fixed;
    z-index: 21;
    display: grid;
    min-width: 140px;
    padding: var(--space-1);
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    border: 2px solid var(--color-accent);
    border-radius: var(--radius-md);
  }

  .card-menu button {
    padding: var(--space-2);
    border: none;
    background: none;
    color: inherit;
    text-align: left;
    font-size: var(--font-size-xs);
    cursor: pointer;
  }

  .card-menu button:hover {
    background: var(--color-md-surface);
  }
</style>
