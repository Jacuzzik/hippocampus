<!-- What the assistant may reach right now and what it has used, read only. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { addedAgents, archived, setArchived } from "../owner/addedAgents.svelte";
  import { AGENT_MODELS, AGENT_PROVIDERS, CARD_FACES, type Caps } from "../control/model";

  type Budget = { caps: { app: Caps; assistant: Caps }; used: { app: Caps; assistant: Caps } };

  type System = { cpu: number; ram: number; swap: number; disk: number; disk_free: number };

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
        engineError = result.error ?? "The engine was not changed.";
        return;
      }
      engine = await invoke<Engine>("sidecar_call", { method: "engine" });
      // Stop the main terminal so the next start runs the new provider; the open panel restarts it.
      await invoke("sidecar_call", { method: "terminal_stop", params: { agent: "hippo" } }).catch(() => undefined);
      window.dispatchEvent(new Event("engine-changed"));
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

  type Watcher = {
    name: string;
    kind: string;
    status: "running" | "stopped" | "error";
    last_event: string | null;
  };

  let budget = $state<Budget | null>(null);
  let watchers = $state<Watcher[]>([]);
  let system = $state<System | null>(null);
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
    const read = () =>
      invoke<System>("sidecar_call", { method: "system" }).then(
        (value) => (system = value),
        (cause) => console.error("Could not read system stats", cause),
      );
    void read();
    const timer = setInterval(read, 5000);
    const tokenTimer = setInterval(() => loadTokens(directories), 60000);
    return () => {
      clearInterval(timer);
      clearInterval(tokenTimer);
    };
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
      watchers = (await invoke<{ watchers: Watcher[] }>("sidecar_call", { method: "watchers" })).watchers;
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
          <div class="head">
            <img src={CARD_FACES.find((f) => f.id === "card-face-17")?.url} alt="" class="pic" />
            <span class="name">Hippoherman</span>
            <span class="badge">MAIN</span>
            <span class="count">{(folderTokens[engine?.folder ?? ""] ?? 0).toLocaleString("en-US")} tok</span>
          </div>
          {#if engine}
            <div class="dir">{engine.folder}</div>
            <div class="picker">
              <span class="k">engine</span>
              <select bind:value={engineProvider} onchange={() => (engineModel = modelOptions[0] ?? "")} aria-label="AI provider">
                {#each AGENT_PROVIDERS as p (p.id)}
                  <option value={p.id}>{p.label}</option>
                {/each}
              </select>
              <select bind:value={engineModel} disabled={!modelOptions.length} aria-label="AI model">
                {#each modelOptions as m (m)}
                  <option value={m}>{m}</option>
                {/each}
              </select>
              <button type="button" class="btn" disabled={!engineChanged} onclick={() => (confirmOpen = true)}>apply</button>
            </div>
            {#if confirmOpen}
              <div class="scrim" role="presentation" onclick={() => (confirmOpen = false)}>
                <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="engine-confirm-title" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === "Escape" && (confirmOpen = false)}>
                  <h3 id="engine-confirm-title">Change the AI engine?</h3>
                  <p>Changing to <strong>{engineProvider}</strong> / <strong>{engineModel}</strong> resets the terminal and starts a new session. The current session cannot be resumed.</p>
                  <div class="actions">
                    <button type="button" class="btn" onclick={() => (confirmOpen = false)}>cancel</button>
                    <button type="button" class="btn" onclick={() => { confirmOpen = false; applyEngine(); }}>apply and reset</button>
                  </div>
                </div>
              </div>
            {/if}
            {#if engineError}<p class="status error">{engineError}</p>{/if}
            {#if engineDone}<p class="status">{engineDone}</p>{/if}
            <div class="meta">
              <span class="k">last tool</span>
              <span>{activity[engine.folder]?.last_tool ?? "none this month"}</span>
            </div>
          {/if}
        </div>
        {#each active as agent (agent.id)}
          <div class="card">
            <div class="head">
              {#if CARD_FACES.find((f) => f.id === agent.character)}
                <img src={CARD_FACES.find((f) => f.id === agent.character)?.url} alt="" class="pic" />
              {:else}
                <div class="pic letter">{agent.name.slice(0, 1).toUpperCase()}</div>
              {/if}
              <span class="name">{agent.name}</span>
            </div>
            <div class="dir">{agent.folder}</div>
            <div class="meta">
              <span class="k">last tool</span>
              <span>{activity[agent.folder]?.last_tool ?? "none this month"}</span>
              <span class="tok">{(folderTokens[agent.folder] ?? 0).toLocaleString("en-US")} tok</span>
            </div>
            <div class="meta">
              <span class="k">last reply</span>
              <span>{activity[agent.folder]?.last_reply ? new Date(activity[agent.folder]?.last_reply ?? "").toLocaleString() : "none this month"}</span>
            </div>
            <div class="meta"><span class="k">model</span><span class="model">{agent.model || "default"}</span></div>
            <div class="row">
              <button type="button" class="btn" onclick={() => setArchived(agent.id, true)}>archive</button>
            </div>
          </div>
        {/each}
        <p class="sigma">Σ {(budget.used.app.monthly + agentTokens).toLocaleString("en-US")} tok <span>this month · all agents and the app</span></p>
      </div>
    </div>

    {#if hidden.length > 0}
      <div class="sec">
        <h3>ARCHIVED <em>{hidden.length}</em></h3>
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
      </div>
    {/if}

    <div class="sec">
      <h3>DIRECTORIES</h3>
      {#if directories.length === 0}
        <p class="muted">No agent folders yet.</p>
      {:else}
        <ul>
          {#each directories as folder (folder)}
            <li class="folder">{folder}</li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="sec">
      <h3>ISSUES</h3>
      {#if directories.length === 0}
        <p class="muted">Add an agent to pick a folder.</p>
      {:else}
        <div class="picker">
          <select bind:value={selectedFolder} aria-label="Folder">
            {#each directories as folder (folder)}
              <option value={folder}>{folder}</option>
            {/each}
          </select>
          <button type="button" class="btn solid" onclick={() => fetchIssues(selectedFolder)}>Fetch issues</button>
        </div>
        <h4>ISSUES FETCHED</h4>
        {#if current?.error}
          <p class="status error">{current.error}</p>
        {:else if current?.list && current.list.length > 0}
          <ul>
            {#each current.list as issue (issue.number)}
              <li>#{issue.number} {issue.title}</li>
            {/each}
          </ul>
        {:else}
          <p class="muted">No issues fetched yet</p>
        {/if}
      {/if}
    </div>

    <div class="sec">
      <h3>WATCHERS</h3>
      {#if watchers.length === 0}
        <p class="muted">No background watchers are set up.</p>
      {:else}
        {#each watchers as watcher, i (i)}
          <div class="watch">
            <i class="dot {watcher.status}"></i>
            <span>{watcher.name}</span>
            <small class="status {watcher.status}">{watcher.status}{watcher.last_event ? `, last ${watcher.last_event}` : ""}</small>
          </div>
        {/each}
      {/if}
    </div>

    <div class="sec">
      <h3>SYSTEM</h3>
      <div class="tiles">
        <div class="tile"><span>CPU</span><b>{system ? `${system.cpu}%` : "…"}</b></div>
        <div class="tile"><span>RAM</span><b>{system ? `${system.ram}%` : "…"}</b></div>
        <div class="tile"><span>SWAP</span><b>{system ? `${system.swap}%` : "…"}</b></div>
        <div class="tile"><span>DISK</span><b>{system ? `${system.disk}%` : "…"}</b></div>
        <div class="tile"><span>FREE</span><b>{system ? `${system.disk_free} GB` : "…"}</b></div>
      </div>
    </div>
  {/if}
</section>

<style>
  .monitor {
    --hippo-purple: #6a58e0;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-3);
    font-family: var(--font-mono);
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
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
    font-weight: 400;
    color: var(--hippo-purple);
  }

  h3 em {
    margin-left: auto;
    font-style: normal;
    font-family: var(--font-mono);
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

  .hero {
    border: 1px solid var(--hippo-purple);
    border-radius: 8px;
    padding: var(--space-3);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    background: linear-gradient(135deg, rgba(106, 88, 224, 0.22), rgba(106, 88, 224, 0.04));
  }

  .big {
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }

  .split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
  }

  .mini {
    border: 1px solid var(--color-md-text-muted);
    border-radius: 6px;
    padding: var(--space-2);
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  h3 em {
    margin-left: auto;
  }

  .tile {
    display: flex;
    flex-direction: column;
    gap: 2px;
    border: 1px solid var(--color-md-text-muted);
    border-radius: 4px;
    padding: var(--space-2);
  }

  .tile span {
    font-size: 9px;
    color: var(--color-md-text-muted);
  }

  .tile b {
    font-weight: 400;
  }

  .tiles {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-1);
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
    border: 2px solid var(--hippo-purple);
    border-top-width: 2px;
    border-radius: 0 0 8px 8px;
    padding: 6px 8px;
    box-shadow: 2px 2px 0 var(--color-md-shadow);
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 10px;
  }

  .head {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .head .name {
    font-size: 11px;
    font-weight: 700;
  }

  .head .count,
  .meta .tok {
    margin-left: auto;
  }

  .dir {
    overflow-wrap: anywhere;
    opacity: 0.75;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .meta .k,
  .picker .k {
    opacity: 0.6;
  }

  .sigma {
    margin: 0;
    padding: 4px 8px;
    border: 1px solid var(--color-md-text-muted);
    border-radius: 6px;
    font-size: 10px;
  }

  .sigma span {
    color: var(--color-md-text-muted);
  }

  .model {
    font-weight: 700;
  }

  .top {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }

  .face {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: var(--color-md-card);
    border: 2px solid var(--hippo-purple);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    color: var(--hippo-purple);
    flex: none;
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

  .na {
    color: var(--color-md-card-text);
    opacity: 0.5;
  }

  .note {
    font-size: 9px;
    color: var(--color-md-text-muted);
  }

  .stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }


  h4 {
    margin: 0;
    font-family: "Press Start 2P", monospace;
    font-size: 7px;
    font-weight: 400;
    color: var(--hippo-purple);
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

  .face.small {
    width: 28px;
    height: 28px;
    border-color: var(--color-md-text-muted);
    color: var(--color-md-text-muted);
    background: transparent;
  }

  .name {
    font-size: 13px;
    font-weight: 700;
  }

  .sub {
    font-size: 10px;
    color: var(--color-md-card-text);
    opacity: 0.7;
  }

  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }

  .k {
    width: 56px;
    font-size: 9px;
    opacity: 0.7;
  }

  .badge {
    margin-left: auto;
    background: var(--hippo-purple);
    color: var(--color-md-card);
    font-size: 8px;
    padding: 3px 6px;
    border-radius: 3px;
  }

  .folder {
    overflow-wrap: anywhere;
  }

  .desc {
    font-size: 10px;
    opacity: 0.85;
  }

  .btn {
    border: 2px solid var(--hippo-purple);
    border-radius: 4px;
    padding: 4px 9px;
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    font: inherit;
    font-size: 10px;
    cursor: pointer;
  }

  .btn.solid {
    background: var(--hippo-purple);
    color: var(--color-md-card);
  }

  .arch {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    border: 1px dashed var(--color-md-text-muted);
    border-radius: 6px;
    padding: var(--space-2);
  }

  .grow {
    flex: 1;
    min-width: 0;
  }

  .card.main {
    border-top-width: 6px;
  }

  .pic {
    width: 22px;
    height: 22px;
  }

  .picker {
    display: flex;
    gap: var(--space-2);
  }

  .picker select {
    flex: 1;
    min-width: 0;
    font: inherit;
    padding: 5px;
    background: var(--color-md-card);
    color: var(--color-md-card-text);
    border: 2px solid var(--hippo-purple);
    border-radius: 4px;
  }

  .net {
    border: 1px solid var(--color-md-text-muted);
    border-radius: 6px;
    padding: var(--space-2);
  }

  .watch {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--color-md-text-muted);
  }

  .watch small {
    margin-left: auto;
    font-size: 9px;
  }

  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--color-md-text-muted);
    flex: none;
  }

  .dot.running,
  .status.running {
    color: var(--hippo-purple);
    background-color: var(--hippo-purple);
  }

  .status {
    color: var(--color-md-text-muted);
  }

  .status.error,
  .dot.error {
    color: var(--color-md-danger);
  }

  .dot.error {
    background: var(--color-md-danger);
  }
  .scrim { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.45); display: grid; place-items: center; z-index: 1000; }
  .dialog { background: var(--surface, #fff); color: inherit; border-radius: 10px; padding: 20px; max-width: 420px; width: calc(100% - 32px); box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35); }
  .dialog h3 { margin: 0 0 8px; font-size: 16px; }
  .dialog p { margin: 0 0 16px; line-height: 1.45; }
  .dialog .actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
