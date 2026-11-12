<!-- The bottom agent row: the main agent first (fixed), then added agents that can be moved. -->
<script lang="ts">
  import { every } from "../poll.ts";
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

  type Account = { claude: boolean; model: string; provider: string };

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

  // Reads the provider and model in use. Runs at start and again when the Monitor tab changes the engine.
  async function loadAccount(): Promise<void> {
    try {
      account = await invoke<Account>("sidecar_call", { method: "account" });
    } catch (cause) {
      console.error("Could not read the provider in use", cause);
    }
  }
  onMount(() => {
    void loadAccount();
    window.addEventListener("engine-changed", loadAccount);
    return () => window.removeEventListener("engine-changed", loadAccount);
  });

  const provider = $derived(
    account ? (AGENT_PROVIDERS.find((p) => p.id === account?.provider)?.label ?? account?.provider) : "...",
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
    // Drop the tool word the terminal puts in front ("Bash: ls ...", "exec ...").
    return shown.map((c) => c.replace(/^\s*(bash|exec|sh|shell|cmd)\b\s*:?\s*/i, "")).join("  ·  ") || NO_DATA;
  };
  // The provider a card's terminal runs (its CLI name), else the agent's own provider: its name and logo.
  const providerOf = (id: string, fallback: string): { name: string; logo?: string } => {
    const word = (live[id]?.command ?? "").split(" ")[0] ?? "";
    return { name: CLI_ID[word] ? labelFor(CLI_ID[word]) : labelOf(fallback), logo: providerLogo(CLI_ID[word] ?? fallback) };
  };
  // The provider HIPPO's terminal actually runs, from its CLI name; the account's provider until a terminal runs.
  // Names come from the Monitor picker list (AGENT_PROVIDERS), so one provider has one name everywhere.
  const labelFor = (id: string): string => AGENT_PROVIDERS.find((p) => p.id === id)?.label ?? id;
  const CLI_ID: Record<string, string> = { claude: "claude", codex: "codex", ollama: "ollama", agy: "antigravity" };
  const cliWord = $derived((live.hippoherman?.command ?? "").split(" ")[0] ?? "");
  const runningProvider = $derived(CLI_ID[cliWord] ? labelFor(CLI_ID[cliWord]) : provider);
  // Fallback is the account's own provider, not a guess: a Codex account with no running CLI must not show Ollama.
  const runningId = $derived(CLI_ID[cliWord] ?? account?.provider ?? "");
  const runningLogo = $derived(providerLogo(runningId));
  async function refreshLive(): Promise<void> {
    for (const id of ["hippoherman", ...added.map((a) => a.id)]) {
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
    return every(() => void refreshLive(), 3000);
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
    class:selected={selection.id === "hippoherman"}
    role="button"
    tabindex="0"
    aria-pressed={selection.id === "hippoherman"}
    onclick={(e) => {
      if ((e.target as HTMLElement).closest("button")) return;
      selectAgent("hippoherman");
    }}
    onkeydown={(e) => {
      if (e.key === "Enter" || e.key === " ") selectAgent("hippoherman");
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
        <span class="val model">{live.hippoherman?.model ?? account?.model ?? NO_DATA}</span>
      </span>
      <span class="row wide cmd-row">
        <span class="val cmd">{cmdOf("hippoherman")}</span>
      </span>
      <span class="row wide" aria-label="Context {live.hippoherman?.percent ?? NO_DATA}">
        <span class="ctx-bar" aria-hidden="true"><span class="ctx-fill" style="width: {live.hippoherman?.percent ?? 0}%"></span></span>
        <span class="pct">{live.hippoherman?.percent != null ? `${live.hippoherman?.percent}%` : NO_DATA}</span>
      </span>
    </div>
    <div class="side">
      <button type="button" class="talk" disabled title="Planned: talking to an agent by voice is not built yet"
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
            provider: runningProvider,
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
          <span class="head"><b>{agent.name}</b></span>
          <span class="row">
            <span class="val provider-line">
              {#if providerOf(agent.id, agent.provider).logo}<span class="provider-logo" style='--logo: url("{providerOf(agent.id, agent.provider).logo}")'></span>{/if}
              <span class="provider-name">{providerOf(agent.id, agent.provider).name}</span>
            </span>
          </span>
          <span class="row">
            <span class="val model">{agent.model || live[agent.id]?.model || "No model set"}</span>
          </span>
          <span class="row wide cmd-row">
            <span class="val cmd">{cmdOf(agent.id)}</span>
          </span>
          <span class="row wide" aria-label="Context {live[agent.id]?.percent ?? NO_DATA}">
            <span class="ctx-bar" aria-hidden="true"><span class="ctx-fill" style="width: {live[agent.id]?.percent ?? 0}%"></span></span>
            <span class="pct">{live[agent.id]?.percent != null ? `${live[agent.id]?.percent}%` : NO_DATA}</span>
          </span>
        </span>
      </button>
      <div class="side">
        <button type="button" class="talk" disabled title="Planned: talking to an agent by voice is not built yet"
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

  .add {
    box-shadow: none;
    flex: none;
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 1px dashed var(--color-border);
    border-radius: var(--radius-md);
    background: none;
    color: var(--color-text-muted);
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
    cursor: pointer;
  }

  .chip button {
    padding: 0 var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text);
    box-shadow: none;
    cursor: pointer;
  }

  .chip .info {
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
  }

  /* HIPPO main card, per the mockup: white body, purple top bar and outline.
     --hippo-purple is the light accent (--color-accent). */
  .chip {
    --hippo-purple: var(--color-accent);
    align-items: flex-start;
    width: 320px;
    min-height: 0;
    padding: 8px 12px 8px;
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    border: 2px solid var(--hippo-purple);
    border-top-width: 8px;
    border-radius: 0 0 2px 2px;
    box-shadow: none;
    font-family: var(--font-ui);
  }

  .chip img.face {
    width: 52px;
    height: 52px;
    margin-top: 4px;
  }

  .chip .text {
    flex: 1;
    min-width: 0;
  }

  .chip b {
    font-size: var(--font-size-lg);
    font-weight: 700;
    line-height: 1.2;
  }

  .chip .badge {
    padding: 3px 6px;
    border-radius: var(--radius-sm);
    background: var(--hippo-purple);
    color: var(--color-md-card);
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
    font-weight: 700;
  }

  /* The logo is drawn in the brand colour: a mask shows the logo's shape, filled with the colour or gradient. */
  .chip .provider-line {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .chip .provider-logo {
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



  .chip .row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--font-size-xs);
    line-height: 1.6;
  }


  .chip .val {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* The model name sits a touch higher than the rows around it. */
  .chip .model {
    position: relative;
    top: -2px;
  }

  /* The CMD text is highlighted like the MAIN badge. */
  /* The command stops short of the TALK and INFO column and ends in "…". */
  .chip .row.wide.cmd-row {
    margin-right: 0;
  }

  .chip .cmd {
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    align-self: flex-start;
    padding: 1px 4px;
    line-height: 1.4;
    border-radius: var(--radius-sm);
    background: var(--hippo-purple);
    color: var(--color-md-card);
    font-weight: 700;
  }

  /* CMD and CTX rows start under the face and run out to the card's right edge. */
  .chip .row.wide {
    margin-left: calc(-52px - var(--space-2));
    margin-right: -12px;
  }

  /* One continuous loading-style bar: the fill's width is the context percentage. */
  .chip .ctx-bar {
    flex: 1;
    min-width: 140px;
    height: 5px;
    border-radius: var(--radius-sm);
    background: var(--color-ctx-track);
    overflow: hidden;
  }

  .chip .ctx-fill {
    display: block;
    height: 100%;
    background: var(--hippo-purple);
  }

  .chip .pct {
    font-size: var(--font-size-tag);
    color: var(--color-md-card-muted);
  }

  .chip .side {
    display: flex;
    flex: none;
    flex-direction: column;
    gap: 6px;
    width: 64px;
    align-self: stretch;
  }

  .chip .talk,
  .chip .info {
    width: 100%;
    height: 26px;
    padding: 0;
    border-radius: var(--radius-sm);
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
    font-weight: 700;
    cursor: pointer;
  }

  .chip .talk {
    border: none;
    background: var(--hippo-purple);
    color: var(--color-md-card);
  }

  .chip .talk:disabled {
    opacity: 1;
    cursor: not-allowed;
  }

  .chip .info {
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
    font-size: var(--font-size-tag);
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
    background: var(--color-shadow-strong);
  }

  .info-box {
    width: min(340px, calc(100vw - 32px));
    padding: var(--space-4);
    background: var(--color-bg-1);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    border-radius: var(--radius-sm);
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
    font-size: var(--font-size-xl);
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
    font-size: var(--font-size-tag);
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
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
  }


  .pct {
    margin-left: 4px;
  }

  .status {
    text-transform: uppercase;
  }

  .talk {
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
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
