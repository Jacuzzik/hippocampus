<!-- The bottom agent row: the main agent first (fixed), then added agents that can be moved. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import logo from "../assets/brand/hippocampus-mark-purple.png";
  import {
    addedAgents,
    agentEdit,
    archived,
    archiveAgent,
    removeAgent,
    saveEdit,
    selectAgent,
    selection,
    startEdit,
  } from "./addedAgents.svelte";
  import { AGENT_PROVIDERS, CARD_FACES, providerLogo } from "../control/model";
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

  // The menu opens at the cursor.
  function openMenu(e: MouseEvent, id: string): void {
    menu = { id, x: e.clientX, bottom: window.innerHeight - e.clientY };
  }

  // The info box for an added agent; the card's INFO button and the menu's Open both use it.
  function showInfo(agent: (typeof added)[number]): void {
    info = {
      name: agent.name,
      role: "Added",
      provider: labelOf(agent.provider),
      model: agent.model,
      folder: agent.folder,
      status: NO_DATA,
      ctx: NO_DATA,
    };
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
    status: string;
    ctx: string;
  } | null>(null);
  const NO_DATA = "—";
  // What each added agent's terminal is running and its context use; read every few seconds.
  let live = $state<Record<string, { command: string | null; status: string | null; percent: number | null; running?: string[]; last?: string | null; model?: string | null }>>({});
  // CMD shows what is running now, else the last command the agent ran.
  const cmdOf = (id: string): string => {
    const info = live[id];
    const shown = info?.running?.length ? info.running : info?.last ? [info.last] : [];
    return shown.join("  ·  ") || NO_DATA;
  };
  // The provider a card's terminal runs (its CLI name), else the agent's own provider: its name and logo.
  const providerOf = (id: string, fallback: string): { name: string; logo?: string } => {
    const word = (live[id]?.command ?? "").split(" ")[0] ?? "";
    return { name: CLI_LABEL[word] ?? labelOf(fallback), logo: providerLogo(CLI_ID[word] ?? fallback) };
  };
  // The provider HIPPO's terminal actually runs, from its CLI name; the account's provider until a terminal runs.
  const CLI_LABEL: Record<string, string> = { claude: "Claude Code", codex: "Codex", ollama: "Ollama", agy: "Antigravity" };
  const CLI_ID: Record<string, string> = { claude: "claude", codex: "codex", ollama: "ollama", agy: "antigravity" };
  const cliWord = $derived((live.hippo?.command ?? "").split(" ")[0] ?? "");
  const runningProvider = $derived(CLI_LABEL[cliWord] ?? provider);
  const runningId = $derived(CLI_ID[cliWord] ?? (account?.claude ? "claude" : "ollama"));
  const runningLogo = $derived(providerLogo(runningId));
  async function refreshLive(): Promise<void> {
    for (const id of ["hippo", ...added.map((a) => a.id)]) {
      try {
        const info = await invoke<{ command: string | null; status: string | null; running?: string[]; last?: string | null; model?: string | null }>("sidecar_call", {
          method: "terminal_command",
          params: { agent: id },
        });
        const percent = info.command
          ? (
              await invoke<{ percent: number }>("sidecar_call", {
                method: "terminal_context",
                params: { agent: id },
              })
            ).percent
          : null;
        live[id] = { command: info.command, status: info.status, percent, running: info.running, last: info.last, model: info.model };
      } catch {
        live[id] = { command: null, status: null, percent: null };
      }
    }
  }
  onMount(() => {
    void refreshLive();
    const timer = setInterval(() => void refreshLive(), 3000);
    return () => clearInterval(timer);
  });

</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key !== "Escape") return;
    info = null;
    menu = null;
    agentEdit.current = null;
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
        const agent = added.find((a) => a.id === open.id);
        menu = null;
        if (agent) showInfo(agent);
      }}>Open</button
    >
    <button
      type="button"
      role="menuitem"
      onclick={() => {
        menu = null;
        startEdit(open.id, "note");
      }}>Add note</button
    >
    <button
      type="button"
      role="menuitem"
      onclick={() => {
        menu = null;
        startEdit(open.id, "rename");
      }}>Rename</button
    >
    <button
      type="button"
      role="menuitem"
      onclick={() => {
        archiveAgent(open.id);
        menu = null;
      }}
      class="danger">Archive</button
    >
    <button
      type="button"
      role="menuitem"
      class="danger"
      onclick={() => {
        removeAgent(open.id);
        menu = null;
      }}>Delete</button
    >
  </div>
{/if}

{#if agentEdit.current}
  <div class="info-scrim" role="presentation" onmousedown={() => (agentEdit.current = null)}>
    <div
      class="info-box"
      role="dialog"
      aria-modal="true"
      aria-label={agentEdit.current.mode === "rename" ? "Rename agent" : "Agent note"}
      tabindex="-1"
      onmousedown={(e) => e.stopPropagation()}
    >
      <header>
        <b>{agentEdit.current.mode === "rename" ? "Rename" : "Note (only you can see this)"}</b>
      </header>
      {#if agentEdit.current.mode === "rename"}
        <input class="edit-field" bind:value={agentEdit.current.value} aria-label="Name" />
      {:else}
        <textarea class="edit-field" rows="5" bind:value={agentEdit.current.value} aria-label="Note"></textarea>
      {/if}
      <div class="edit-actions">
        <button type="button" onclick={() => (agentEdit.current = null)}>Cancel</button>
        <button type="button" onclick={saveEdit}>Save</button>
      </div>
    </div>
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
        <dt>STATUS</dt>
        <dd>{info.status}</dd>
        <dt>CTX</dt>
        <dd>{info.ctx}</dd>
      </dl>
    </div>
  </div>
{/if}

<div class="agent-bar" aria-label="Agents">
  <!-- Selecting HIPPO's card highlights it; the Control Room stays in the right panel. Its buttons do their own job. -->
  <div
    class="chip main"
    class:selected={selection.id === "hippo"}
    role="button"
    tabindex="0"
    aria-pressed={selection.id === "hippo"}
    onclick={(e) => {
      if ((e.target as HTMLElement).closest("button")) return;
      selectAgent("hippo");
    }}
    onkeydown={(e) => {
      if (e.key === "Enter" || e.key === " ") selectAgent("hippo");
    }}
  >
    <img src={CARD_FACES.find((f) => f.id === "card-face-17")?.url ?? logo} alt="" class="face" />
    <div class="text">
      <span class="head">
        <b>Hippoherman</b>
        <span class="badge">MAIN</span>
      </span>
      <span class="row">
        <span class="val provider-line">
          {#if runningLogo}<span class="provider-logo" style='--logo: url("{runningLogo}")'></span>{/if}
          <span class="provider-name">{runningProvider}</span>
        </span>
      </span>
      <span class="row">
        <span class="val model">{live.hippo?.model ?? account?.model ?? NO_DATA}</span>
      </span>
      <span class="row wide">
        <span class="val cmd">{cmdOf("hippo")}</span>
      </span>
      <span class="row wide" aria-label="Context {live.hippo?.percent ?? NO_DATA}">
        <span class="ctx-bar" aria-hidden="true"><span class="ctx-fill" style="width: {live.hippo?.percent ?? 0}%"></span></span>
        <span class="pct">{live.hippo?.percent != null ? `${live.hippo?.percent}%` : NO_DATA}</span>
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
            name: "Hippoherman",
            role: "Main · fixed",
            provider,
            model: account?.model ?? "Loading model",
            folder: "",
            status: ORB_LABELS[assistant.chat.orb],
            ctx: NO_DATA,
          })}>INFO</button
      >
      <span class="status">{assistant.chat.orb === "thinking" ? "Working" : "Idle"}</span>
    </div>
  </div>
  {#each added as agent (agent.id)}
    <div class="chip main added" class:selected={selection.id === agent.id}>
      <button
        type="button"
        class="card-open"
        aria-haspopup="menu"
        aria-label="{agent.name} options"
        aria-pressed={selection.id === agent.id}
        onclick={() => selectAgent(agent.id)}
        oncontextmenu={(e) => {
          e.preventDefault();
          openMenu(e, agent.id);
        }}
      >
        <img src={CARD_FACES.find((f) => f.id === agent.character)?.url ?? logo} alt="" class="face" />
        <span class="text">
          <span class="head"><b>{agent.name}</b>
            <span class="val provider-line">
              {#if providerOf(agent.id, agent.provider).logo}<span class="provider-logo" style='--logo: url("{providerOf(agent.id, agent.provider).logo}")'></span>{/if}
              <span class="provider-name">{providerOf(agent.id, agent.provider).name}</span>
            </span>
          </span>
          <span class="row">
            <span class="val">{live[agent.id]?.model || agent.model || "No model set"}</span>
          </span>
          <span class="row wide">
            <span class="val cmd">{cmdOf(agent.id)}</span>
          </span>
          <span class="row wide" aria-label="Context {live[agent.id]?.percent ?? NO_DATA}">
            <span class="ctx-bar" aria-hidden="true"><span class="ctx-fill" style="width: {live[agent.id]?.percent ?? 0}%"></span></span>
            <span class="pct">{live[agent.id]?.percent != null ? `${live[agent.id]?.percent}%` : NO_DATA}</span>
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
          onclick={() => showInfo(agent)}>INFO</button
        >
        <span class="status">{live[agent.id]?.status === "Working" ? "Working" : "Idle"}</span>
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

  /* The logo is drawn in the brand colour: a mask shows the logo's shape, filled with the colour or gradient. */
  .chip.main .provider-line {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .chip.main .provider-logo {
    width: 12px;
    height: 12px;
    flex: none;
    background: currentColor;
    -webkit-mask-image: var(--logo);
    mask-image: var(--logo);
    -webkit-mask-size: contain;
    mask-size: contain;
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-position: center;
    mask-position: center;
  }


  /* Normal cards lost their provider row; this holds the space it used so they keep their height. */
  .chip.main.added .head {
    margin-bottom: 22px;
    position: relative;
  }

  /* Sits in the 22px gap under the name, so the card keeps its height. */
  .chip.main.added .head .provider-line {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 3px;
  }

  .chip.main .row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    line-height: 1.6;
  }


  .chip.main .val {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* The model name sits a touch higher than the rows around it. */
  .chip.main .model {
    position: relative;
    top: -2px;
  }

  /* The CMD text is highlighted like the MAIN badge. */
  .chip.main .cmd {
    align-self: flex-start;
    padding: 1px 4px;
    line-height: 1.4;
    border-radius: 3px;
    background: var(--hippo-purple);
    color: var(--color-md-card);
    font-weight: 700;
  }

  /* CMD and CTX rows start under the face and run out to the card's right edge. */
  .chip.main .row.wide {
    margin-left: calc(-52px - var(--space-2));
    margin-right: -12px;
  }

  /* One continuous loading-style bar: the fill's width is the context percentage. */
  .chip.main .ctx-bar {
    flex: 1;
    min-width: 140px;
    height: 5px;
    border-radius: 3px;
    background: rgba(106, 88, 224, 0.2);
    overflow: hidden;
  }

  .chip.main .ctx-fill {
    display: block;
    height: 100%;
    background: var(--hippo-purple);
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
  /* The 6px less top border is made up in padding, so the card is as tall as HIPPO's. */
  .chip.main.added {
    border-top-width: 2px;
    padding-top: 14px;
    box-shadow: none;
  }

  /* The card whose panel is open in the right panel. */
  .chip.main.selected {
    outline: 2px solid var(--hippo-purple);
    outline-offset: 2px;
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

  .edit-field {
    box-sizing: border-box;
    width: 100%;
    font: inherit;
    padding: var(--space-2);
    background: var(--color-bg-0);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 0;
  }

  .edit-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
    margin-top: var(--space-3);
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
    background: var(--color-bg-1);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 0;
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
    background: var(--color-surface);
  }

  /* Archive and Delete sit under a divider, in red, as in the office app's menu. */
  .card-menu .danger {
    margin-top: 4px;
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-border);
    color: var(--color-danger);
  }
</style>
