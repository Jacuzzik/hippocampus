<script lang="ts">
  import "./control.css";
  import { invoke } from "@tauri-apps/api/core";
  import { getVersion } from "@tauri-apps/api/app";
  import { onMount } from "svelte";
  import BudgetSection from "./BudgetSection.svelte";
  import ConnectorsSection from "./ConnectorsSection.svelte";
  import KeysSection from "./KeysSection.svelte";
  import MemorySection from "./MemorySection.svelte";
  import NetworkSection from "./NetworkSection.svelte";
  import Dropdown from "../controls/Dropdown.svelte";
  import StatusCard from "../controls/StatusCard.svelte";
  import Tabs from "../controls/Tabs.svelte";
  import { crashLog, type CrashRow } from "../crashLog.svelte.ts";
  import { FONT_MAX, FONT_MIN, prefs, type Intro, type Motion } from "../prefs.svelte.ts";
  import { SETTINGS_PAGES, type SettingsPage } from "./model";

  // Settings as pages: a list of categories on the left, one short page on the right.
  // Each setting has one home. Day-to-day controls (dispatch, jobs, questions) stay in the Control panel.
  let { onclose }: { onclose: () => void } = $props();

  type Saved = {
    general: { vault: string | null; network: string };
    agents: { provider: string; model: string; ollama: string };
    budgets: { max_tool_calls: number };
    memory: { max_bytes: number };
  };

  let page = $state<SettingsPage>("General");
  let sidecar = $state("Checking…");
  let saved = $state<Saved | null>(null);
  let version = $state("");
  let query = $state("");

  const items = $derived(
    SETTINGS_PAGES.filter((p) => !query.trim() || `${p.id} ${p.words}`.toLowerCase().includes(query.trim().toLowerCase())).map((p) => ({
      id: p.id,
      label: p.id,
    })),
  );
  // Typing in the search box jumps to the first page that matches.
  $effect(() => {
    const first = items[0];
    if (query.trim() && first && !items.some((i) => i.id === page)) page = first.id as SettingsPage;
  });

  // Changing the vault: the backend opens the folder first, so a bad path is never saved.
  let vaultDraft = $state("");
  let vaultBusy = $state(false);
  let vaultNote = $state<string | null>(null);
  let vaultError = $state<string | null>(null);
  async function changeVault(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    vaultBusy = true;
    vaultNote = vaultError = null;
    try {
      const opened = await invoke<{ vault: string; notes?: number }>("sidecar_call", {
        method: "set_vault",
        params: { vault: vaultDraft.trim() },
      });
      if (saved) saved.general.vault = opened.vault;
      vaultNote = `Opened ${opened.vault}. The graph and note list update in a few seconds.`;
      vaultDraft = "";
    } catch (cause) {
      vaultError = String(cause);
    } finally {
      vaultBusy = false;
    }
  }

  // The error log on disk, newest first. An older backend without it falls back to this window's rows.
  let diskRows = $state<CrashRow[] | null>(null);
  const errorRows = $derived(diskRows ?? [...crashLog.rows].reverse());
  $effect(() => {
    if (page !== "Privacy and data") return;
    invoke<{ crashes: CrashRow[] }>("sidecar_call", { method: "crashes" }).then(
      (value) => (diskRows = value.crashes),
      () => (diskRows = null),
    );
  });
  function clearErrors(): void {
    crashLog.clear();
    invoke<{ crashes: CrashRow[] }>("sidecar_call", { method: "clear_crashes" }).then(
      (value) => (diskRows = value.crashes),
      () => (diskRows = null),
    );
  }

  onMount(async () => {
    getVersion().then(
      (v) => (version = v),
      () => (version = "unknown"),
    );
    try {
      saved = await invoke<Saved>("sidecar_call", { method: "settings" });
      sidecar = "Running";
    } catch (cause) {
      sidecar = `Not running: ${String(cause)}`;
    }
  });

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }
</script>

<div class="scrim" role="presentation" onmousedown={onclose}>
  <div class="box" role="dialog" aria-modal="true" aria-label="Settings" tabindex="-1" onkeydown={onKey} onmousedown={(e) => e.stopPropagation()}>
    <header>
      <h2>Settings</h2>
      <input type="search" aria-label="Search settings" placeholder="Search settings" bind:value={query} />
      <button type="button" class="close" aria-label="Close settings" onclick={onclose}>×</button>
    </header>
    <div class="body">
      <nav class="rail">
        {#if items.length}
          <Tabs {items} bind:value={page} label="Settings pages" idBase="settings" vertical />
        {:else}
          <p class="muted">No page matches "{query}".</p>
        {/if}
      </nav>
      <div class="page" role="tabpanel" id="settings-panel" aria-labelledby={`settings-tab-${page}`} tabindex="-1">
        {#if page === "General"}
          <section class="control-section">
            <h3>General</h3>
            <div class="setting">
              <div><b>Vault folder</b><p>Where your notes live. To change it, type a folder that exists and open it.</p></div>
              <code>{saved ? (saved.general.vault ?? "Not chosen") : "…"}</code>
            </div>
            <form class="row" onsubmit={changeVault}>
              <input type="text" aria-label="New vault folder" placeholder="/home/you/notes" bind:value={vaultDraft} />
              <button type="submit" disabled={!vaultDraft.trim() || vaultBusy}>{vaultBusy ? "Opening…" : "Open folder"}</button>
            </form>
            {#if vaultNote}<p class="muted" role="status">{vaultNote}</p>{/if}
            {#if vaultError}<p class="error" role="alert">{vaultError}</p>{/if}
            <div class="setting">
              <div><b>Open on the last tab</b><p>The Control Room opens on the tab you used last.</p></div>
              <label class="switch"><input type="checkbox" bind:checked={prefs.rememberTab} /><span>{prefs.rememberTab ? "On" : "Off"}</span></label>
            </div>
            <div class="setting">
              <div><b>Settings file</b><p>Backend settings are also in this file. No keys are stored in it.</p></div>
              <code>config/settings.toml</code>
            </div>
          </section>
        {:else if page === "Appearance"}
          <section class="control-section">
            <h3>Appearance</h3>
            <div class="setting">
              <div><b>Motion</b><p>System follows your computer's reduced-motion setting.</p></div>
              <Dropdown
                label="Motion"
                value={prefs.motion}
                options={[
                  { value: "system", label: "System" },
                  { value: "on", label: "On" },
                  { value: "off", label: "Off" },
                ]}
                onchange={(next) => (prefs.motion = next as Motion)}
              />
            </div>
            <div class="setting">
              <div><b>Start-up logo</b><p>How long the logo stays once the app has loaded. Applies from the next start.</p></div>
              <Dropdown
                label="Start-up logo"
                value={prefs.intro}
                options={[
                  { value: "long", label: "Long (10 s)" },
                  { value: "short", label: "Short (1 s)" },
                  { value: "off", label: "Off" },
                ]}
                onchange={(next) => (prefs.intro = next as Intro)}
              />
            </div>
            <div class="setting">
              <div><b>Terminal text size</b><p>Used by every agent terminal. {FONT_MIN} to {FONT_MAX} px.</p></div>
              <span class="stepper">
                <button type="button" aria-label="Smaller terminal text" disabled={prefs.terminalFontSize <= FONT_MIN} onclick={() => (prefs.terminalFontSize -= 1)}>−</button>
                <output>{prefs.terminalFontSize}px</output>
                <button type="button" aria-label="Larger terminal text" disabled={prefs.terminalFontSize >= FONT_MAX} onclick={() => (prefs.terminalFontSize += 1)}>+</button>
              </span>
            </div>
            <div class="setting">
              <div><b>Font</b><p>One monospace face everywhere, bundled with the app.</p></div>
              <code>JetBrains Mono</code>
            </div>
            <div class="setting">
              <div><b>Reset appearance</b><p>Back to 12 px text, system motion and remembering the last tab.</p></div>
              <button type="button" onclick={() => prefs.reset()}>Reset</button>
            </div>
          </section>
          <div class="cards">
            <StatusCard name="Light theme" what="A light set of colours next to the dark one." status="Planned" reason="Every colour is a token now, so this needs a second token set and a contrast pass." />
          </div>
        {:else if page === "Agents"}
          <section class="control-section">
            <h3>Agents</h3>
            <div class="setting">
              <div><b>Main agent engine</b><p>Change it on the Monitor tab of the Control Room.</p></div>
              <code>{saved ? `${saved.agents.provider} · ${saved.agents.model}` : "…"}</code>
            </div>
            <div class="setting">
              <div><b>Tool calls per request</b><p>The most tools the assistant may call for one request.</p></div>
              <code>{saved ? saved.budgets.max_tool_calls : "…"}</code>
            </div>
          </section>
          <NetworkSection />
        {:else if page === "Budgets"}
          <BudgetSection />
        {:else if page === "Models and keys"}
          <KeysSection />
        {:else if page === "Connectors"}
          <ConnectorsSection />
        {:else if page === "Memory"}
          <section class="control-section">
            <h3>Memory</h3>
            <div class="setting">
              <div><b>Memory size per agent</b><p>Notes past this size are condensed.</p></div>
              <code>{saved ? `${saved.memory.max_bytes.toLocaleString()} bytes` : "…"}</code>
            </div>
          </section>
          <MemorySection />
        {:else if page === "Privacy and data"}
          <section class="control-section">
            <h3>Privacy and data</h3>
            <div class="setting">
              <div><b>Your data</b><p>Sign out or remove your data in Setup and account, on the left ribbon.</p></div>
            </div>
            <div class="setting">
              <div>
                <b>Error log</b>
                <p>Errors from this window and the backend, kept on this computer in <code>crashes.jsonl</code>. Never sent.</p>
              </div>
              <span class="row">
                <code>{errorRows.length} recorded</code>
                <button type="button" disabled={errorRows.length === 0} onclick={clearErrors}>Clear</button>
              </span>
            </div>
            {#if errorRows.length}
              <ul class="log" aria-label="Recorded errors">
                {#each errorRows.slice(0, 10) as row, index (index)}
                  <li><span class="muted">{row.at.slice(0, 19).replace("T", " ")}</span> <b>{row.source}</b> {row.message}</li>
                {/each}
              </ul>
            {/if}
          </section>
          <div class="cards">
            <StatusCard name="Telemetry" what="Anonymous usage numbers, off unless you turn them on." status="Planned" reason="Nothing is collected today." />
          </div>
        {:else if page === "Advanced"}
          <section class="control-section">
            <h3>Advanced</h3>
            <div class="setting">
              <div><b>Backend (Python sidecar)</b><p>Answers every request from this window.</p></div>
              <code>{sidecar}</code>
            </div>
          </section>
          <div class="cards">
            <StatusCard name="Dictation and meeting capture" what="Speak into any field and capture meeting notes." status="Planned" reason="No speech-to-text source is set up in this build." />
            <StatusCard name="Logs viewer" what="Read backend logs here instead of a terminal." status="Planned" reason="The backend does not write a rotating log file yet." />
          </div>
        {:else}
          <section class="control-section">
            <h3>About</h3>
            <div class="setting">
              <div><b>Hippocampus</b><p>A local notes vault with a graph and real command-line agents.</p></div>
              <code>{version ? `v${version}` : "…"}</code>
            </div>
          </section>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 20;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--color-bg-0) 70%, transparent);
  }

  .box {
    display: flex;
    flex-direction: column;
    width: min(920px, calc(100vw - 2 * var(--space-4)));
    height: min(640px, 85vh);
    padding: var(--space-4);
    color: var(--color-text);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    border-radius: var(--radius-sm);
    box-shadow: var(--layout-drawer-shadow);
  }

  header {
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-lg);
  }

  header input {
    flex: 1;
    min-width: 0;
    max-width: 320px;
    margin-left: auto;
    padding: var(--space-1) var(--space-2);
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .close {
    padding: 0 var(--space-2);
    color: var(--color-text-muted);
    font-size: var(--font-size-lg);
    background: none;
    border: 0;
    cursor: pointer;
  }

  .body {
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    gap: var(--space-4);
    flex: 1;
    min-height: 0;
    margin-top: var(--space-3);
  }

  .rail {
    overflow-y: auto;
    padding-right: var(--space-2);
    border-right: 1px solid var(--color-border);
  }

  .page {
    min-width: 0;
    overflow-y: auto;
    padding-right: var(--space-2);
  }

  .setting {
    display: flex;
    gap: var(--space-4);
    align-items: center;
    justify-content: space-between;
    padding: var(--space-2) 0;
    border-top: 1px solid var(--color-border);
  }

  .setting:first-of-type {
    border-top: 0;
  }

  .setting p {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .setting code {
    max-width: 50%;
    color: var(--color-text-muted);
    overflow-wrap: anywhere;
    text-align: right;
  }

  .switch,
  .stepper {
    display: inline-flex;
    gap: var(--space-2);
    align-items: center;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-2);
    margin-top: var(--space-3);
  }

  .log {
    margin: var(--space-2) 0 0;
    padding: 0;
    font-size: var(--font-size-xs);
    list-style: none;
  }

  .log li {
    overflow-wrap: anywhere;
  }

  .muted {
    color: var(--color-text-muted);
  }

  @media (max-width: 700px) {
    .body {
      grid-template-columns: 1fr;
      grid-template-rows: auto minmax(0, 1fr);
    }

    .rail {
      border-right: 0;
    }
  }
</style>
