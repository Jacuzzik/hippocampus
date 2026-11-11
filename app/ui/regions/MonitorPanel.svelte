<!-- What the assistant may reach right now and what it has used, read only. -->
<script lang="ts">
  import { every } from "../poll.ts";
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { addedAgents, archived, removeAgent, setArchived } from "../owner/addedAgents.svelte";
  import { AGENT_MODELS, AGENT_PROVIDERS, CARD_FACES, type Caps } from "../control/model";
  import Dropdown from "../controls/Dropdown.svelte";

  type Budget = { caps: { app: Caps; assistant: Caps }; used: { app: Caps; assistant: Caps } };

  // Only the agents the user added (addedAgents store); archived ones show a REOPEN button.
  const active = $derived(addedAgents.list.filter((a) => !archived.ids.includes(a.id)));
  const hidden = $derived(addedAgents.list.filter((a) => archived.ids.includes(a.id)));

  // Unique folders of the agents the user added (agents with no folder are left out).

  type Issue = { number: number; title: string; url: string };
  // Per directory: the issues fetched on request, or the reason they could not be read.
  let issues = $state<Record<string, { list?: Issue[]; error?: string }>>({});
  let selectedFolder = $state("");
  // The main agent's engine as the app has it set (read only: no call changes it yet).
  type Engine = { provider: string; model: string; folder: string };
  type Activity = { tool_calls: number; last_tool: string | null; last_reply: string | null };
  // Per agent folder, this month: real Claude Code activity from the session files.
  let activity = $state<Record<string, Activity>>({});
  let engine = $state<Engine | null>(null);
  // The main agent's folder is included, so its card gets its own token count.
  const directories = $derived([...new Set([engine?.folder, ...addedAgents.list.map((a) => a.folder)].filter(Boolean))] as string[]);
  // Second step of delete: the card asks again before it removes the agent.
  let confirmDelete = $state<string | null>(null);

  function providerLabel(id: string): string {
    return AGENT_PROVIDERS.find((p) => p.id === id)?.label ?? id;
  }

  // Stops the agent's running terminal; the card stays.
  async function stopAgent(id: string): Promise<void> {
    await invoke("sidecar_call", { method: "terminal_stop", params: { agent: id } }).catch(() => undefined);
  }

  let engineProvider = $state("");
  let engineModel = $state("");
  let engineError = $state("");
  let engineDone = $state("");
  // The current model is listed first when the provider has not changed.
  const modelOptions = $derived.by(() => {
    const list = AGENT_MODELS[engineProvider] ?? [];
    const now = engine && engine.provider === engineProvider ? engine.model : "";
    return now && !list.includes(now) ? [now, ...list] : list;
  });
  // Apply asks first: it resets the terminal and starts a new session that cannot be resumed.
  let confirmOpen = $state(false);
  const engineChanged = $derived(!!engine && (engineProvider !== engine.provider || engineModel !== engine.model));

  // Checked before the confirm dialog: a provider or model this app does not offer shows its reason at once.
  const engineIssue = $derived.by(() => {
    if (!AGENT_PROVIDERS.some((p) => p.id === engineProvider)) return `${engineProvider || "This provider"} is not a provider in this app.`;
    const list = AGENT_MODELS[engineProvider] ?? [];
    if (!list.length) return `${engineProvider} has no models in this app to pick from.`;
    if (!list.includes(engineModel)) return `${engineModel || "No model"} is not a model ${engineProvider} offers in this app.`;
    return "";
  });
  function askApply(): void {
    engineDone = "";
    engineError = engineIssue;
    if (!engineIssue) confirmOpen = true;
  }

  async function applyEngine(): Promise<void> {
    engineError = "";
    engineDone = "";
    try {
      // The sidecar answers { ok, error } for a refused change, so a refusal shows here, not as silence.
      const result = await invoke<{ ok: boolean; error?: string; message?: string }>("sidecar_call", {
        method: "set_engine",
        params: { provider: engineProvider, model: engineModel },
      });
      if (!result.ok) {
        engineError = result.error ?? "The model was not changed.";
        return;
      }
      engine = await invoke<Engine>("sidecar_call", { method: "engine" });
      // Stop the main terminal so the next start runs the new provider; the open panel restarts it.
      await invoke("sidecar_call", { method: "terminal_stop", params: { agent: "hippoherman" } }).catch(() => undefined);
      window.dispatchEvent(new CustomEvent("engine-changed", { detail: { provider: engineProvider, model: engineModel } }));
      engineDone = result.message ?? "Saved.";
    } catch (cause) {
      engineError = String(cause);
    }
  }
  const current = $derived(issues[selectedFolder]);
  $effect(() => {
    if (!directories.includes(selectedFolder)) selectedFolder = directories[0] ?? "";
  });

  async function fetchIssues(folder: string): Promise<void> {
    try {
      const result = await invoke<{ issues?: Issue[]; error?: string }>("sidecar_call", {
        method: "issues",
        params: { folder },
      });
      issues[folder] = result.error ? { error: result.error } : { list: result.issues ?? [] };
    } catch (cause) {
      console.error("Could not fetch the issues", cause);
      issues[folder] = { error: "Could not reach the app's helper." };
    }
  }

  let budget = $state<Budget | null>(null);
  let failed = $state(false);
  // Tokens per agent folder this month, from each agent's Claude Code sessions (real transcripts).
  let folderTokens = $state<Record<string, number>>({});
  const agentTokens = $derived(Object.values(folderTokens).reduce((sum, n) => sum + n, 0));

  function loadTokens(folders: string[]): void {
    if (folders.length === 0) return;
    invoke<{ folders: Record<string, number>; activity: Record<string, Activity> }>("sidecar_call", {
      method: "tokens",
      params: { folders },
    }).then(
      (value) => {
        folderTokens = value.folders;
        activity = value.activity;
      },
      (cause) => console.error("Could not read agent tokens", cause),
    );
  }

  $effect(() => {
    loadTokens(directories);
  });

  onMount(() => {
    return every(() => loadTokens(directories), 60000);
  });

  onMount(async () => {
    try {
      budget = await invoke<Budget>("sidecar_call", { method: "budget" });
      // Kept apart so an old helper without this call does not hide the rest of the monitor.
      invoke<Engine>("sidecar_call", { method: "engine" }).then(
        (value) => {
          engine = value;
          engineProvider = value.provider;
          engineModel = value.model;
        },
        (cause) => console.error("Could not read the engine", cause),
      );
    } catch (cause) {
      failed = true;
      console.error("Could not read the monitor", cause);
    }
  });
</script>

<section class="monitor" aria-label="Monitor">
  {#if failed}
    <p class="muted">Could not read the monitor.</p>
  {:else if !budget}
    <p class="muted">Checking…</p>
  {:else}
    <div class="sec">
      <h3>AGENTS<em>{active.length + 1} active · {hidden.length} archived</em></h3>
      {#if active.length === 0}
        <p class="muted">No agents yet. Agents you add appear here.</p>
      {/if}
      <div class="cards">
        <div class="card main">
          <div class="title-row">
            <img src={CARD_FACES.find((f) => f.id === "card-face-17")?.url} alt="" class="pic big" />
            <div class="title-text">
              <div class="title-line">
                <span class="title">Hippoherman</span>
                <span class="badge">MAIN</span>
              </div>
              {#if engine}<span class="subtitle">{providerLabel(engine.provider)}</span>
              <span class="subtitle">{engine.model}</span>{/if}
            </div>
          </div>
          {#if engine}
            <div class="dir">{engine.folder}</div>
            <div class="picker">
              <Dropdown
                bind:value={engineProvider}
                options={AGENT_PROVIDERS.map((p) => ({ value: p.id, label: p.label }))}
                label="AI provider"
                onchange={() => (engineModel = modelOptions[0] ?? "")}
              />
              <Dropdown
                bind:value={engineModel}
                options={modelOptions.map((m) => ({ value: m, label: m }))}
                label="AI model"
                disabled={!modelOptions.length}
              />
              <button type="button" class="btn" disabled={!engineChanged} onclick={askApply}>apply</button>
            </div>
            {#if confirmOpen}
              <div class="scrim" role="presentation" onclick={() => (confirmOpen = false)}>
                <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="engine-confirm-title" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === "Escape" && (confirmOpen = false)}>
                  <h3 id="engine-confirm-title">Change the AI model?</h3>
                  <p>Changing to <strong>{engineProvider}</strong> / <strong>{engineModel}</strong> resets the terminal and starts a new session. The current session cannot be resumed.</p>
                  <div class="actions">
                    <button type="button" class="btn" onclick={() => (confirmOpen = false)}>cancel</button>
                    <button type="button" class="btn solid" onclick={() => { confirmOpen = false; applyEngine(); }}>apply and reset</button>
                  </div>
                </div>
              </div>
            {/if}
            {#if engineError}<p class="status error">{engineError}</p>{/if}
            {#if engineDone}<p class="status">{engineDone}</p>{/if}
            <div class="meta">
              <span class="lastran">{activity[engine.folder]?.last_tool ? `${activity[engine.folder]?.last_tool} - last ran` : "none this month"}</span>
            </div>
            <div class="row">
              <span class="zone-tag">DANGER ZONE</span>
              <button type="button" class="btn danger" onclick={() => stopAgent("hippoherman")}>stop</button>
            </div>
          {/if}
        </div>
        {#each active as agent (agent.id)}
          <div class="card">
            <div class="title-row">
              {#if CARD_FACES.find((f) => f.id === agent.character)}
                <img src={CARD_FACES.find((f) => f.id === agent.character)?.url} alt="" class="pic big" />
              {:else}
                <div class="pic big letter">{agent.name.slice(0, 1).toUpperCase()}</div>
              {/if}
              <div class="title-text">
                <div class="title-line">
                  <span class="title">{agent.name}</span>
                  <span class="tok">{(folderTokens[agent.folder] ?? 0).toLocaleString("en-US")} tok</span>
                </div>
                <span class="subtitle">{providerLabel(agent.provider)}</span>
                <span class="subtitle">{agent.model || "default"}</span>
              </div>
            </div>
            <div class="dir">{agent.folder}</div>
            <div class="meta">
              <span class="lastran">{activity[agent.folder]?.last_tool ? `${activity[agent.folder]?.last_tool} - last ran` : "none this month"}</span>
            </div>
            <div class="row">
              <span class="zone-tag">DANGER ZONE</span>
              <div class="row-btns">
              <button type="button" class="btn danger" onclick={() => stopAgent(agent.id)}>stop</button>
              {#if confirmDelete === agent.id}
                <button type="button" class="btn confirm" onclick={() => { removeAgent(agent.id); confirmDelete = null; }}>confirm delete</button>
              {:else}
                <button type="button" class="btn danger" onclick={() => (confirmDelete = agent.id)}>delete</button>
              {/if}
              <button type="button" class="btn danger" onclick={() => setArchived(agent.id, true)}>archive</button>
              </div>
            </div>
          </div>
        {/each}
        <p class="sigma">Σ {(budget.used.app.monthly + agentTokens).toLocaleString("en-US")} tok <span>burned this month</span></p>
      </div>
    </div>

    {#if hidden.length > 0}
      <details class="sec fold">
        <summary><h3>ARCHIVED <em>{hidden.length}</em></h3></summary>
        {#each hidden as agent (agent.id)}
          <div class="arch">
            {#if CARD_FACES.find((f) => f.id === agent.character)}
              <img src={CARD_FACES.find((f) => f.id === agent.character)?.url} alt="" class="pic small" />
            {:else}
              <div class="pic small letter">{agent.name.slice(0, 1).toUpperCase()}</div>
            {/if}
            <div class="grow">
              <div class="name">{agent.name}</div>
              <div class="sub">{agent.folder}</div>
            </div>
            <button type="button" class="btn solid" onclick={() => setArchived(agent.id, false)}>REOPEN</button>
          </div>
        {/each}
      </details>
    {/if}

    <div class="sec">
      <h3>DIRECTORIES & ISSUES</h3>
      {#if directories.length === 0}
        <p class="muted">No agent folders yet.</p>
      {:else}
        <ul>
          {#each directories as folder (folder)}
            <li class="folder">{folder}</li>
          {/each}
        </ul>
        <div class="picker">
          <Dropdown bind:value={selectedFolder} options={directories.map((f) => ({ value: f, label: f }))} label="Folder" />
          <button type="button" class="btn solid" onclick={() => fetchIssues(selectedFolder)}>Fetch issues</button>
        </div>
        {#if current?.error}
          <p class="status error">{current.error}</p>
        {:else if current?.list && current.list.length > 0}
          <ul>
            {#each current.list as issue (issue.number)}
              <li>#{issue.number} {issue.title}</li>
            {/each}
          </ul>
        {:else if current?.list}
          <p class="status error">No issues were fetched for this folder. It may have no open issues, or gh could not reach its GitHub repo.</p>
        {:else}
          <p class="muted">Pick a folder and press Fetch issues.</p>
        {/if}
      {/if}
    </div>

  {/if}
</section>

<style>
  .monitor {
    --hippo-purple: var(--color-accent);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-3);
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  .sec {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  h3 {
    margin: 0;
    padding-bottom: var(--space-1);
    border-bottom: 1px solid var(--color-md-text-muted);
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
    font-weight: 400;
    color: var(--hippo-purple);
  }

  h3 em {
    margin-left: auto;
    font-style: normal;
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text-muted);
  }

  p {
    margin: 0;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    padding: var(--space-1) 0;
  }

  .muted {
    color: var(--color-md-text-muted);
  }

  .big {
    font-size: var(--font-size-xl);
    font-weight: 700;
    letter-spacing: -0.5px;
  }

  h3 em {
    margin-left: auto;
  }

  .cards {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  /* Same chip style as the agent bar: cream card, accent border, thick top edge. */
  .card {
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    border: 2px solid var(--color-accent);
    border-top-width: 8px;
    border-radius: 0 0 2px 2px;
    padding: 16px 18px;
    box-shadow: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--font-size-tag);
  }

  /* Token count sits on the name line, at the right edge. */
  .title-line .tok {
    margin-left: auto;
    flex: none;
    font-size: var(--font-size-tag);
  }

  .dir {
    overflow-wrap: anywhere;
    opacity: 0.75;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-1) var(--space-2);
  }

  /* The "tokens this month" line: no background or border, centred, a bit bigger. */
  .sigma {
    margin: 0;
    text-align: center;
    padding: 8px 12px;
    background: transparent;
    color: var(--color-md-text);
    border: 0;
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
  }

  .sigma span {
    color: var(--color-md-text-muted);
  }

  /* Agent picture: the card face image, square, no circle. */
  .pic {
    width: 32px;
    height: 32px;
    object-fit: cover;
    border-radius: 0;
    border: none;
    flex: none;
  }

  .pic.small {
    width: 32px;
    height: 32px;
  }



  .pic.letter {
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-md-card);
    border: 2px solid var(--hippo-purple);
    color: var(--hippo-purple);
    font-weight: 700;
  }

  .name {
    font-size: var(--font-size-sm);
    font-weight: 700;
  }

  .sub {
    font-size: var(--font-size-tag);
    color: var(--color-md-card-text);
    opacity: 0.7;
  }

  .row {
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    align-items: center;
  }

  .badge {
    flex: none;
    background: var(--hippo-purple);
    color: var(--color-md-card);
    font-size: var(--font-size-tag);
    padding: 3px 6px;
    border-radius: var(--radius-sm);
  }

  /* Directory names wrap onto more lines by default, never cut off. */
  .folder {
    white-space: normal;
    overflow-wrap: anywhere;
  }

  .btn {
    height: var(--layout-control-h);
    padding: 0 var(--space-3);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    font: inherit;
    font-size: var(--font-size-sm);
    font-weight: 500;
    white-space: nowrap;
    box-shadow: none;
    cursor: pointer;
  }

  .btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .btn.solid {
    background: var(--color-accent);
    border-color: var(--color-accent);
    color: var(--color-accent-on);
  }

  /* Card buttons (stop, delete, archive): solid red, white text. */
  .btn.danger {
    background: var(--color-md-danger);
    border-color: var(--color-md-danger);
    color: #ffffff;
  }

  /* Confirm delete: solid orange, white text. */
  .btn.confirm {
    background: var(--color-pending);
    border-color: var(--color-pending);
    color: #ffffff;
  }

  .row-btns {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  /* The bottom strip of a card is red (the danger colour). */
  .row {
    background: var(--color-md-danger);
    padding: 10px 18px;
    /* Reaches past the card's 2px accent border so the red covers it at the sides and bottom. */
    margin: 0 -20px -18px;
  }

  /* DANGER ZONE as a white badge with bold red text. */
  .zone-tag {
    background: #ffffff;
    color: var(--color-md-danger);
    border: 1px solid #ffffff;
    font-size: var(--font-size-tag);
    font-weight: 700;
    padding: 3px 6px;
    border-radius: var(--radius-sm);
  }

  .arch {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    border: 1px dashed var(--color-md-text-muted);
    border-radius: var(--radius-sm);
    padding: var(--space-2);
  }

  .grow {
    flex: 1;
    min-width: 0;
  }

  /* Title block: face and name big, provider and model in smaller lines under them. */
  .title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .title-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }

  /* Name and MAIN badge on one line, the badge right after the name. */
  .title-line {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
  }

  .title {
    min-width: 0;
    font-size: var(--font-size-md);
    font-weight: 700;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .subtitle {
    font-size: var(--font-size-xs);
    color: var(--color-md-text-subtle);
  }

  .pic.big {
    width: 40px;
    height: 40px;
  }

  /* The last command sits in an accent pill, as in the bottom-bar cards. */
  .lastran {
    font-family: var(--font-mono);
    font-weight: 700;
    background: var(--color-accent);
    color: var(--color-md-card);
    padding: 4px 6px;
    border-radius: var(--radius-sm);
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pic {
    width: 22px;
    height: 22px;
  }

  .picker {
    display: flex;
    gap: var(--space-2);
  }


  /* Collapsible groups (archived): click the heading to open or close. No colour or border. */
  .fold > summary {
    cursor: pointer;
    list-style: revert;
  }

  .fold > summary h3 {
    display: inline;
  }

  .status.error {
    color: var(--color-md-danger);
  }
  .scrim { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6); display: grid; place-items: center; z-index: 1000; }
  /* Dark confirm box, the app's dark palette, with a warning bar on its left edge. */
  .dialog { background: var(--color-md-surface); color: var(--color-md-text); border: 1px solid var(--color-md-border); border-left: 3px solid var(--color-accent); border-radius: var(--radius-sm); padding: var(--space-4); max-width: 420px; width: calc(100% - 32px); box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); }
  .dialog h3 { margin: 0 0 var(--space-2); font-size: var(--font-size-md); font-weight: 600; color: var(--color-md-text); }
  .dialog p { margin: 0 0 var(--space-4); font-size: var(--font-size-sm); line-height: 1.45; color: var(--color-md-text-muted); }
  .dialog p strong { color: var(--color-md-text); font-weight: 600; }
  .dialog .actions { display: flex; justify-content: flex-end; gap: var(--space-2); }
  .dialog .btn.solid { background: var(--color-md-accent); color: var(--color-md-accent-on); border-color: var(--color-md-accent); }
</style>
