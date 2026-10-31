<!-- The bottom agent row: the main agent first (fixed), then added agents that can be moved. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import logo from "../assets/brand/hippocampus-mark-purple.png";
  import {
    addedAgents,
    archived,
    setArchived,
  } from "./addedAgents.svelte";
  import { AGENT_PROVIDERS, AVATARS, CARD_FACES } from "../control/model";
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
  // The HIPPO card's context bar has eight segments; none are filled until the app reports context use.
  const CTX_SEGMENTS = Array.from({ length: 8 }, (_, i) => i);
  // An added agent keeps its character id; show the avatar's name.
  const faceOf = (id: string): string =>
    AVATARS.find((a) => a.id === id)?.name ?? NO_DATA;

</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key !== "Escape") return;
    info = null;
    menu = null;
  }}
/>

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
    <img src={CARD_FACES.find((f) => f.id === "card-face-17")?.url ?? logo} alt="" class="face" />
    <div class="text">
      <span class="head">
        <b>HIPPO</b>
        <span class="badge">BOSS</span>
      </span>
      <span class="online">
        <span class="dot" class:on={account !== null}></span>
        {account ? "ONLINE" : NO_DATA}
      </span>
      <span class="row">
        <span class="key">MODEL</span>
        <span class="val">{account?.model ?? NO_DATA}</span>
      </span>
      <span class="row">
        <span class="key">CMD</span>
        <span class="val">{NO_DATA}</span>
      </span>
      <span class="row" aria-label="Context {NO_DATA}">
        <span class="key">CTX</span>
        <span class="segs" aria-hidden="true">
          {#each CTX_SEGMENTS as seg (seg)}<span class="seg"></span>{/each}
        </span>
        <span class="pct">{NO_DATA}</span>
      </span>
    </div>
    <div class="side">
      <button type="button" class="talk" disabled title="Talk is not set up yet"
        >TALK</button
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
      <span class="status">{ORB_LABELS[assistant.chat.orb]}</span>
    </div>
  </div>
  {#each added as agent (agent.id)}
    <div class="chip main added">
      <button
        type="button"
        class="card-open"
        aria-haspopup="menu"
        aria-label="{agent.name} options"
        onclick={(e) => openMenu(e, agent.id)}
      >
        <img src={CARD_FACES.find((f) => f.id === agent.character)?.url ?? logo} alt="" class="face" />
        <span class="text">
          <span class="head"><b>{agent.name}</b><span class="badge spacer" aria-hidden="true">BOSS</span></span>
          <span class="online"><span class="dot"></span>{NO_DATA}</span>
          <span class="row">
            <span class="key">MODEL</span>
            <span class="val">{agent.model || NO_DATA}</span>
          </span>
          <span class="row">
            <span class="key">CMD</span>
            <span class="val">{NO_DATA}</span>
          </span>
          <span class="row" aria-label="Context {NO_DATA}">
            <span class="key">CTX</span>
            <span class="segs" aria-hidden="true">
              {#each CTX_SEGMENTS as seg (seg)}<span class="seg"></span>{/each}
            </span>
            <span class="pct">{NO_DATA}</span>
          </span>
        </span>
      </button>
      <div class="side">
        <button type="button" class="talk" disabled title="Talk is not set up yet"
          >TALK</button
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
        <span class="status">{ORB_LABELS[assistant.chat.orb]}</span>
      </div>
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

  /* HIPPO main card, per the mockup: white body, purple top bar and outline.
     shortcut: the purple is hardcoded because .md-theme remaps --color-accent to lilac and no token holds #6A58E0; move it to design/tokens.json. */
  .chip.main {
    --hippo-purple: #6a58e0;
    align-items: flex-start;
    width: 320px;
    min-height: 0;
    padding: 8px 12px 8px;
    background: #ffffff;
    color: var(--color-md-card-text);
    border: 2px solid var(--hippo-purple);
    border-top-width: 8px;
    border-radius: 0 0 10px 10px;
    box-shadow: none;
    font-family: var(--font-mono);
  }

  .chip.main img.face {
    width: 52px;
    height: 52px;
    margin-top: 4px;
  }

  .chip.main .text {
    flex: 1;
    min-width: 0;
  }

  .chip.main b {
    font-size: 16px;
    font-weight: 700;
    line-height: 1.2;
  }

  .chip.main .badge {
    padding: 3px 6px;
    border-radius: 3px;
    background: var(--hippo-purple);
    color: var(--color-md-card);
    font-family: var(--font-mono);
    font-size: 9px;
    font-weight: 700;
  }

  .chip.main .online {
    margin: 2px 0 4px;
    font-size: 10px;
    opacity: 1;
    color: var(--color-md-card-text);
  }

  .chip.main .dot.on {
    background: #149c6a;
  }

  .chip.main .row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    line-height: 1.6;
  }

  .chip.main .key {
    width: 44px;
    flex: none;
    font-size: 8px;
    color: var(--color-md-card-muted);
  }

  .chip.main .val {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .chip.main .segs {
    display: inline-flex;
    gap: 3px;
  }

  .chip.main .seg {
    width: 12px;
    height: 5px;
    border-radius: 3px;
    background: var(--hippo-purple);
    opacity: 0.2;
  }

  .chip.main .pct {
    font-size: 10px;
    color: var(--color-md-card-muted);
  }

  .chip.main .side {
    display: flex;
    flex: none;
    flex-direction: column;
    gap: 6px;
    width: 64px;
    align-self: stretch;
  }

  .chip.main .talk,
  .chip.main .info {
    width: 100%;
    height: 26px;
    padding: 0;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 700;
    cursor: pointer;
  }

  .chip.main .talk {
    border: none;
    background: var(--hippo-purple);
    color: var(--color-md-card);
  }

  .chip.main .talk:disabled {
    opacity: 1;
    cursor: not-allowed;
  }

  .chip.main .info {
    border: 1px solid var(--hippo-purple);
    background: var(--color-md-card);
    color: var(--hippo-purple);
  }


  /* Added agents: HIPPO's layout and outline, but no purple accent top line. */
  .chip.main.added {
    border-top-width: 2px;
    box-shadow: none;
  }

  /* Hidden BOSS-tag slot: keeps the name on HIPPO's line without showing the tag. */
  .chip.main.added .badge.spacer {
    visibility: hidden;
  }

  /* The card-open button wraps the text, so it takes HIPPO's font and column layout. */
  .chip.main.added .card-open {
    flex: 1;
    min-width: 0;
    align-items: flex-start;
    font: inherit;
    line-height: inherit;
    border-radius: 0;
    box-shadow: none;
  }

  .chip.main .status {
    margin-top: auto;
    align-self: flex-end;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--hippo-purple);
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

  .head {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .badge {
    padding: 1px 3px;
    border-radius: var(--radius-sm);
    background: var(--color-accent);
    color: var(--color-accent-on);
    font-family: "Press Start 2P", monospace;
    font-size: 6px;
  }

  .online {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    opacity: 0.8;
  }

  .dot {
    width: 8px;
    height: 8px;
    flex: none;
    border-radius: 50%;
    background: var(--color-md-text-subtle);
  }

  .dot.on {
    background: var(--color-md-confirm);
  }

  .bar {
    display: inline-block;
    width: 60px;
    height: 6px;
    overflow: hidden;
    border-radius: 3px;
    background: var(--color-md-border);
    vertical-align: middle;
  }

  .fill {
    display: block;
    width: 0;
    height: 100%;
    background: var(--color-md-accent);
  }

  .pct {
    margin-left: 4px;
  }

  .status {
    text-transform: uppercase;
  }

  .talk {
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
  }

  .talk:disabled {
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
