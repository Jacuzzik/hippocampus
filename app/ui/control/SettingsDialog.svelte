<script lang="ts">
  import PlannedSection from "./PlannedSection.svelte";
  import TokensSection from "./TokensSection.svelte";
  import SettingRow from "../controls/SettingRow.svelte";
  import Toggle from "../controls/Toggle.svelte";
  import { dialogFocus } from "../controls/dialogFocus.ts";
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
  import {
    FONT_MAX,
    FONT_MIN,
    prefs,
    SCROLLBACK_MAX,
    SCROLLBACK_MIN,
    type Bell,
    type Cursor,
    type Density,
    type TextSize,
    type Intro,
    type Motion,
    type Theme,
  } from "../prefs.svelte.ts";
  import { SETTINGS_PAGES, type SettingsPage } from "./model";
  import { SHORTCUTS } from "../shortcuts.ts";
  import { FLAGS, flagOn, setFlag } from "../flags.svelte.ts";

  // Settings as pages: a list of categories on the left, one short page on the right.
  // Each setting has one home. Day-to-day controls (dispatch, jobs, questions) stay in the Control panel.
  let {
    onclose,
    start = "General",
  }: { onclose: () => void; start?: SettingsPage } = $props();

  type Saved = {
    general: { vault: string | null; network: string };
    agents: { provider: string; model: string; ollama: string };
    budgets: { max_tool_calls: number };
    memory: { max_bytes: number };
    shell?: Shell;
  };
  // Whether every agent has a shell, and the rules in force, in the backend's own words.
  type Shell = {
    on: boolean;
    sandbox_available: boolean;
    main: string[];
    agents: string[];
    note: string;
  };
  let shellError = $state<string | null>(null);
  async function setShell(on: boolean): Promise<void> {
    shellError = null;
    try {
      const next = await invoke<Shell>("sidecar_call", {
        method: "set_agent_shell",
        params: { on },
      });
      if (saved) saved.shell = next;
    } catch (cause) {
      shellError = String(cause);
    }
  }

  // `start` is only the first page; later changes of the prop are not followed.
  // svelte-ignore state_referenced_locally
  let page = $state<SettingsPage>(start);
  let sidecar = $state("Checking…");
  let saved = $state<Saved | null>(null);
  let version = $state("");

  // Settings as text, to move them to another computer. Keys live in the keychain and are never part of it.
  let importDraft = $state("");
  let transferNote = $state<string | null>(null);
  let transferError = $state<string | null>(null);
  async function exportSettings(): Promise<void> {
    transferNote = transferError = null;
    try {
      const found = await invoke<{ text: string }>("sidecar_call", {
        method: "settings_export",
      });
      await navigator.clipboard.writeText(found.text);
      transferNote = "Settings copied.";
    } catch (cause) {
      transferError = String(cause);
    }
  }
  async function importSettings(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    transferNote = transferError = null;
    try {
      const done = await invoke<{ restart: string }>("sidecar_call", {
        method: "settings_import",
        params: { text: importDraft },
      });
      importDraft = "";
      transferNote = `Settings imported. ${done.restart}`;
    } catch (cause) {
      transferError = String(cause);
    }
  }
  let query = $state("");

  const items = $derived(
    SETTINGS_PAGES.filter((p) => p.id !== "Connectors" || flagOn("connectors"))
      .filter(
        (p) =>
          !query.trim() ||
          `${p.id} ${p.words}`
            .toLowerCase()
            .includes(query.trim().toLowerCase()),
      )
      .map((p) => ({
        id: p.id,
        label: p.id,
      })),
  );
  // Typing in the search box jumps to the first page that matches.
  $effect(() => {
    const first = items[0];
    if (query.trim() && first && !items.some((i) => i.id === page))
      page = first.id as SettingsPage;
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
      const opened = await invoke<{ vault: string; notes?: number }>(
        "sidecar_call",
        {
          method: "set_vault",
          params: { vault: vaultDraft.trim() },
        },
      );
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
    invoke<{ crashes: CrashRow[] }>("sidecar_call", {
      method: "clear_crashes",
    }).then(
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

  // The Doctor page: one list of checks from the backend, read when the page opens.
  type Check = {
    name: string;
    state: "ok" | "warn" | "bad";
    found: string;
    fix: string;
  };
  let doctor = $state<{
    checks: Check[];
    summary: { ok: number; warn: number; bad: number };
  } | null>(null);
  let doctorError = $state<string | null>(null);
  async function readDoctor(): Promise<void> {
    doctorError = null;
    try {
      doctor = await invoke("sidecar_call", { method: "doctor" });
    } catch (cause) {
      doctorError = String(cause);
    }
  }
  $effect(() => {
    if (page === "Doctor" && doctor === null && !doctorError) void readDoctor();
    if (page === "Doctor" && links === null && !linksError) void readLinks();
  });

  // Link doctor: links that point at no note, and notes nothing links to. Read only.
  type Links = {
    notes: number;
    broken_count: number;
    lonely_count: number;
    broken: { note: string; link: string }[];
    lonely: string[];
  };
  let links = $state<Links | null>(null);
  let linksError = $state<string | null>(null);
  async function readLinks(): Promise<void> {
    linksError = null;
    try {
      links = await invoke<Links>("sidecar_call", { method: "link_doctor" });
    } catch (cause) {
      linksError = String(cause);
    }
  }

  // The backend log file, newest lines last. Read when the Advanced page opens and on Refresh.
  let logLines = $state<string[] | null>(null);
  let logPath = $state("");
  let logError = $state<string | null>(null);
  async function readLogs(): Promise<void> {
    logError = null;
    try {
      const found = await invoke<{ path: string; lines: string[] }>(
        "sidecar_call",
        { method: "logs", params: { limit: 200 } },
      );
      logLines = found.lines;
      logPath = found.path;
    } catch (cause) {
      logError = String(cause);
    }
  }
  $effect(() => {
    if (page === "Advanced" && logLines === null && !logError) void readLogs();
  });

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }
</script>

<div class="scrim" role="presentation" onmousedown={onclose}>
  <div
    class="box"
    role="dialog"
    aria-modal="true"
    aria-label="Settings"
    tabindex="-1"
    use:dialogFocus
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    <header>
      <h2>Settings</h2>
      <input
        type="search"
        aria-label="Search settings"
        placeholder="Search settings"
        bind:value={query}
      />
      <button
        type="button"
        class="close"
        aria-label="Close settings"
        onclick={onclose}>×</button
      >
    </header>
    <div class="body">
      <nav class="rail">
        {#if items.length}
          <Tabs
            {items}
            bind:value={page}
            label="Settings pages"
            idBase="settings"
            vertical
          />
        {:else}
          <p class="muted">No page matches "{query}".</p>
        {/if}
      </nav>
      <div
        class="page"
        role="tabpanel"
        id="settings-panel"
        aria-labelledby={`settings-tab-${page}`}
        tabindex="-1"
      >
        {#if page === "General"}
          <section class="control-section">
            <h3>General</h3>
            <SettingRow title="Vault folder"
              >{#snippet help()}Where your notes live. To change it, type a
                folder that exists and open it.{/snippet}
              <code>{saved ? (saved.general.vault ?? "Not chosen") : "…"}</code>
            </SettingRow>
            <form class="row" onsubmit={changeVault}>
              <input
                type="text"
                aria-label="New vault folder"
                placeholder="/home/you/notes"
                bind:value={vaultDraft}
              />
              <button type="submit" disabled={!vaultDraft.trim() || vaultBusy}
                >{vaultBusy ? "Opening…" : "Open folder"}</button
              >
            </form>
            {#if vaultNote}<p class="muted" role="status">{vaultNote}</p>{/if}
            {#if vaultError}<p class="error" role="alert">{vaultError}</p>{/if}
            <SettingRow title="Open on the last tab"
              >{#snippet help()}The Control Room opens on the tab you used last.{/snippet}
              <Toggle
                bind:checked={prefs.rememberTab}
                ariaLabel="Open on the last tab"
                label={prefs.rememberTab ? "On" : "Off"}
              />
            </SettingRow>
            <SettingRow title="Move settings to another computer"
              >{#snippet help()}Copy gives the settings as text. Paste that text
                here on the other computer and press Import. Keys are never
                included.{/snippet}
              <button type="button" onclick={() => void exportSettings()}
                >Copy settings</button
              >
            </SettingRow>
            <form class="row" onsubmit={importSettings}>
              <textarea
                rows="2"
                aria-label="Settings text to import"
                placeholder="Paste settings text here"
                bind:value={importDraft}></textarea>
              <button type="submit" disabled={!importDraft.trim()}
                >Import</button
              >
            </form>
            {#if transferNote}<p class="muted" role="status">
                {transferNote}
              </p>{/if}
            {#if transferError}<p class="error" role="alert">
                {transferError}
              </p>{/if}
            <SettingRow title="Settings file"
              >{#snippet help()}Backend settings are also in this file. No keys
                are stored in it.{/snippet}
              <code>config/settings.toml</code>
            </SettingRow>
          </section>
        {:else if page === "Appearance"}
          <section class="control-section">
            <h3>Appearance</h3>
            <SettingRow title="Theme"
              >{#snippet help()}System follows your computer's light or dark
                setting.{/snippet}
              <Dropdown
                label="Theme"
                value={prefs.theme}
                options={[
                  { value: "dark", label: "Dark" },
                  { value: "light", label: "Light" },
                  { value: "system", label: "System" },
                ]}
                onchange={(next) => (prefs.theme = next as Theme)}
              />
            </SettingRow>
            <SettingRow title="Text size"
              >{#snippet help()}All text outside the terminals. The terminals
                have their own size below.{/snippet}
              <Dropdown
                label="Text size"
                value={prefs.textSize}
                options={[
                  { value: "normal", label: "Normal" },
                  { value: "large", label: "Large" },
                  { value: "larger", label: "Larger" },
                ]}
                onchange={(next) => (prefs.textSize = next as TextSize)}
              />
            </SettingRow>
            <SettingRow title="Density"
              >{#snippet help()}Compact tightens the gaps between things.{/snippet}
              <Dropdown
                label="Density"
                value={prefs.density}
                options={[
                  { value: "comfortable", label: "Comfortable" },
                  { value: "compact", label: "Compact" },
                ]}
                onchange={(next) => (prefs.density = next as Density)}
              />
            </SettingRow>
            <SettingRow title="Motion"
              >{#snippet help()}System follows your computer's reduced-motion
                setting.{/snippet}
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
            </SettingRow>
            <SettingRow title="Quiet mode"
              >{#snippet help()}Turns movement off and slows the background
                refresh of the tabs to one fifth. Good on a battery.{/snippet}
              <Toggle
                bind:checked={prefs.quiet}
                ariaLabel="Quiet mode"
                label={prefs.quiet ? "On" : "Off"}
              />
            </SettingRow>
            <SettingRow title="Start-up logo"
              >{#snippet help()}How long the logo stays once the app has loaded.
                Applies from the next start.{/snippet}
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
            </SettingRow>
            <SettingRow title="Terminal text size"
              >{#snippet help()}Used by every agent terminal. {FONT_MIN} to {FONT_MAX}
                px.{/snippet}
              <span class="stepper">
                <button
                  type="button"
                  aria-label="Smaller terminal text"
                  disabled={prefs.terminalFontSize <= FONT_MIN}
                  onclick={() => (prefs.terminalFontSize -= 1)}>−</button
                >
                <output>{prefs.terminalFontSize}px</output>
                <button
                  type="button"
                  aria-label="Larger terminal text"
                  disabled={prefs.terminalFontSize >= FONT_MAX}
                  onclick={() => (prefs.terminalFontSize += 1)}>+</button
                >
              </span>
            </SettingRow>
            <SettingRow title="Terminal scrollback"
              >{#snippet help()}Lines kept above the screen in every agent
                terminal. {SCROLLBACK_MIN} to {SCROLLBACK_MAX}.{/snippet}
              <input
                type="number"
                aria-label="Terminal scrollback lines"
                min={SCROLLBACK_MIN}
                max={SCROLLBACK_MAX}
                step="500"
                value={prefs.terminalScrollback}
                onchange={(e) =>
                  (prefs.terminalScrollback = Number(e.currentTarget.value))}
              />
            </SettingRow>
            <SettingRow title="Terminal cursor"
              >{#snippet help()}The shape of the cursor in every agent terminal.{/snippet}
              <Dropdown
                label="Terminal cursor"
                value={prefs.terminalCursor}
                options={[
                  { value: "block", label: "Block" },
                  { value: "bar", label: "Bar" },
                  { value: "underline", label: "Underline" },
                ]}
                onchange={(next) => (prefs.terminalCursor = next as Cursor)}
              />
            </SettingRow>
            <SettingRow title="Copy on select"
              >{#snippet help()}Selecting text in an agent terminal copies it to
                the clipboard.{/snippet}
              <Toggle
                bind:checked={prefs.terminalCopyOnSelect}
                ariaLabel="Copy on select"
                label={prefs.terminalCopyOnSelect ? "On" : "Off"}
              />
            </SettingRow>
            <SettingRow title="Terminal bell"
              >{#snippet help()}What an agent terminal does when its program
                rings the bell. Flash lights the border once; there is no sound.{/snippet}
              <Dropdown
                label="Terminal bell"
                value={prefs.terminalBell}
                options={[
                  { value: "off", label: "Off" },
                  { value: "flash", label: "Flash" },
                ]}
                onchange={(next) => (prefs.terminalBell = next as Bell)}
              />
            </SettingRow>
            <SettingRow title="Font"
              >{#snippet help()}One monospace face everywhere, bundled with the
                app.{/snippet}
              <code>JetBrains Mono</code>
            </SettingRow>
            <SettingRow title="Reset appearance"
              >{#snippet help()}Back to the dark theme, 12 px text, system
                motion and remembering the last tab.{/snippet}
              <button type="button" onclick={() => prefs.reset()}>Reset</button>
            </SettingRow>
          </section>
        {:else if page === "Agents"}
          <section class="control-section">
            <h3>Agents</h3>
            <SettingRow title="Main agent engine"
              >{#snippet help()}Change it on the Monitor tab of the Control
                Room.{/snippet}
              <code
                >{saved
                  ? `${saved.agents.provider} · ${saved.agents.model}`
                  : "…"}</code
              >
            </SettingRow>
            <SettingRow title="Tool calls per request"
              >{#snippet help()}The most tools the assistant may call for one
                request.{/snippet}
              <code>{saved ? saved.budgets.max_tool_calls : "…"}</code>
            </SettingRow>
          </section>
          <section class="control-section">
            <h3>Shell and sandbox</h3>
            <SettingRow title="Shell for every agent"
              >{#snippet help()}On: each agent can run simple shell commands,
                and its program runs in a sandbox that keeps the app and the
                system read-only. Off: only the main agent has a shell. Applies
                the next time an agent starts.{/snippet}
              <Toggle
                ariaLabel="Shell for every agent"
                checked={saved?.shell?.on ?? false}
                disabled={!saved?.shell?.sandbox_available}
                onchange={(on) => void setShell(on)}
                label={saved?.shell?.on ? "On" : "Off"}
              />
            </SettingRow>
            {#if shellError}<p class="error" role="alert">{shellError}</p>{/if}
            {#if saved?.shell}
              <p class="hint">{saved.shell.note}</p>
              <h4>Rules in force: main agent</h4>
              <ul class="rules" aria-label="Main agent rules">
                {#each saved.shell.main as line (line)}<li>{line}</li>{/each}
              </ul>
              <h4>Rules in force: other agents</h4>
              <ul class="rules" aria-label="Other agents' rules">
                {#each saved.shell.agents as line (line)}<li>{line}</li>{/each}
              </ul>
            {/if}
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
            <SettingRow title="Memory size per agent"
              >{#snippet help()}Notes past this size are condensed.{/snippet}
              <code
                >{saved
                  ? `${saved.memory.max_bytes.toLocaleString()} bytes`
                  : "…"}</code
              >
            </SettingRow>
          </section>
          <MemorySection />
        {:else if page === "Privacy and data"}
          <section class="control-section">
            <h3>Privacy and data</h3>
            <SettingRow title="Your data"
              >{#snippet help()}Sign out or remove your data in Setup and
                account, on the left ribbon.{/snippet}
            </SettingRow>
            <h4>What leaves this computer</h4>
            <SettingRow title="Messages to your model provider"
              >{#snippet help()}What you type to the assistant or an agent goes
                to the provider you chose (Claude, OpenAI and so on), with your
                own key or login, under that provider's terms. The network
                switch in the Control panel can stop it.{/snippet}
              <code>Only when you chat</code>
            </SettingRow>
            <SettingRow title="Local model (Ollama)"
              >{#snippet help()}Runs on this computer. Nothing leaves it.{/snippet}
              <code>Stays here</code>
            </SettingRow>
            <SettingRow title="GitHub issues"
              >{#snippet help()}Asked through the gh tool with your own login.
                The app stores no GitHub token.{/snippet}
              <code>Only when you look</code>
            </SettingRow>
            <SettingRow title="Your notes"
              >{#snippet help()}Stay in your vault folder. They leave only when
                an agent you run reads one and sends it to its provider.{/snippet}
              <code>Stay here</code>
            </SettingRow>
            <SettingRow title="Usage statistics"
              >{#snippet help()}Nothing is collected or sent about how you use
                the app.{/snippet}
              <code>None</code>
            </SettingRow>
            <SettingRow title="Error log"
              >{#snippet help()}Errors from this window and the backend, kept on
                this computer in <code>crashes.jsonl</code>. Never sent.{/snippet}
              <span class="row">
                <code>{errorRows.length} recorded</code>
                <button
                  type="button"
                  disabled={errorRows.length === 0}
                  onclick={clearErrors}>Clear</button
                >
              </span>
            </SettingRow>
            {#if errorRows.length}
              <ul class="log" aria-label="Recorded errors">
                {#each errorRows.slice(0, 10) as row, index (index)}
                  <li>
                    <span class="muted"
                      >{row.at.slice(0, 19).replace("T", " ")}</span
                    > <b>{row.source}</b>
                    {row.message}
                  </li>
                {/each}
              </ul>
            {/if}
          </section>
          <div class="cards">
            <StatusCard
              name="Telemetry"
              what="Anonymous usage numbers, off unless you turn them on."
              status="Planned"
              reason="Nothing is collected today."
            />
          </div>
        {:else if page === "Advanced"}
          <section class="control-section">
            <h3>Advanced</h3>
            <SettingRow title="Backend (Python)"
              >{#snippet help()}Answers every request from this window.{/snippet}
              <code>{sidecar}</code>
            </SettingRow>
          </section>
          <section class="control-section">
            <h3>Feature switches</h3>
            <p class="hint">
              Turn a part of the app off without a new build. A change applies
              the next time that part opens.
            </p>
            {#each FLAGS as flag (flag.id)}
              <SettingRow title={flag.name}>
                {#snippet help()}{flag.what}{/snippet}
                <Toggle
                  ariaLabel={flag.name}
                  checked={flagOn(flag.id)}
                  onchange={(on) => setFlag(flag.id, on)}
                  label={flagOn(flag.id) ? "On" : "Off"}
                />
              </SettingRow>
            {/each}
          </section>
          <section class="control-section">
            <h3>Backend log</h3>
            <SettingRow title="Newest 200 lines"
              >{#snippet help()}{logPath ||
                  "The backend writes one log file and keeps three older copies. Keys are masked."}{/snippet}
              <button type="button" onclick={() => void readLogs()}
                >Refresh</button
              >
            </SettingRow>
            {#if logError}
              <p class="error" role="alert">{logError}</p>
            {:else if logLines && logLines.length === 0}
              <p class="muted">The log is empty.</p>
            {:else if logLines}
              <pre class="backend-log" aria-label="Backend log">{logLines.join(
                  "\n",
                )}</pre>
            {/if}
          </section>
          <div class="cards">
            <StatusCard
              name="Dictation and meeting capture"
              what="Speak into any field and capture meeting notes."
              status="Planned"
              reason="No speech-to-text source is set up in this build."
            />
          </div>
        {:else if page === "Keyboard"}
          <section class="control-section">
            <h3>Keyboard</h3>
            <table class="keys">
              <thead>
                <tr><th>Keys</th><th>What it does</th><th>Where</th></tr>
              </thead>
              <tbody>
                {#each SHORTCUTS as row (row.keys + row.where)}
                  <tr>
                    <td><kbd>{row.keys}</kbd></td>
                    <td>{row.does}</td>
                    <td>{row.where}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </section>
        {:else if page === "Design tokens"}
          <TokensSection />
        {:else if page === "Planned"}
          <PlannedSection />
        {:else if page === "Doctor"}
          <section class="control-section">
            <h3>Doctor</h3>
            <p class="hint">
              Everything the app needs, checked in one go. Each gap says what to
              do next. Nothing is changed by looking.
            </p>
            <SettingRow
              title={doctor
                ? `${doctor.summary.ok} fine, ${doctor.summary.warn} to look at, ${doctor.summary.bad} to fix`
                : "Checking…"}
            >
              <button type="button" onclick={() => void readDoctor()}
                >Check again</button
              >
            </SettingRow>
            {#if doctorError}<p class="error" role="alert">
                {doctorError}
              </p>{/if}
            {#if doctor}
              <ul class="checks" aria-label="Checks">
                {#each doctor.checks as check (check.name)}
                  <li>
                    <span class="state {check.state}"
                      >{check.state === "ok"
                        ? "Fine"
                        : check.state === "warn"
                          ? "Look"
                          : "Fix"}</span
                    >
                    <div>
                      <b>{check.name}</b>
                      <p>{check.found}</p>
                      {#if check.fix}<p class="fix">{check.fix}</p>{/if}
                    </div>
                  </li>
                {/each}
              </ul>
            {/if}
          </section>
          <section class="control-section" aria-label="Link doctor">
            <h3>Links in your notes</h3>
            <SettingRow
              title={links
                ? `${links.notes} notes, ${links.broken_count} broken ${links.broken_count === 1 ? "link" : "links"}, ${links.lonely_count} with no links`
                : linksError
                  ? "Not checked"
                  : "Checking…"}
            >
              {#snippet help()}A broken link points at a note that does not
                exist. Nothing is repaired here; open the note to fix it.{/snippet}
              <button type="button" onclick={() => void readLinks()}
                >Check again</button
              >
            </SettingRow>
            {#if linksError}<p class="error" role="alert">{linksError}</p>{/if}
            {#if links && links.broken.length > 0}
              <ul class="checks" aria-label="Broken links">
                {#each links.broken as row, i (i)}
                  <li>
                    <span class="state bad">Fix</span>
                    <div>
                      <b>{row.note}</b>
                      <p>links to "{row.link}", which is not a note.</p>
                    </div>
                  </li>
                {/each}
              </ul>
            {/if}
            {#if links && links.lonely.length > 0}
              <ul class="checks" aria-label="Notes with no links">
                {#each links.lonely as path (path)}
                  <li>
                    <span class="state warn">Look</span>
                    <div><b>{path}</b></div>
                  </li>
                {/each}
              </ul>
            {/if}
          </section>
        {:else}
          <section class="control-section">
            <h3>About</h3>
            <SettingRow title="Hippocampus"
              >{#snippet help()}A local notes vault with a graph and real
                command-line agents.{/snippet}
              <code>{version ? `v${version}` : "…"}</code>
            </SettingRow>
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
    min-width: 28px;
    min-height: 28px;
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

  .checks {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .checks li {
    display: flex;
    gap: var(--space-3);
    align-items: baseline;
    padding: var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .checks p {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }

  .checks .fix {
    color: var(--color-text);
  }

  .checks .state {
    flex: none;
    min-width: 40px;
    font-size: var(--font-size-tag);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-success);
  }

  .checks .state.warn {
    color: var(--color-think);
  }

  .checks .state.bad {
    color: var(--color-danger);
  }

  .rules {
    margin: 0;
    padding-left: var(--space-4);
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }

  .backend-log {
    max-height: 260px;
    margin: 0;
    padding: var(--space-2);
    overflow: auto;
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    white-space: pre;
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .keys {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .keys th,
  .keys td {
    padding: var(--space-2);
    text-align: left;
    border-bottom: 1px solid var(--color-border);
  }

  .keys th {
    color: var(--color-text-muted);
    font-weight: normal;
  }

  kbd {
    padding: 0 var(--space-1);
    font: inherit;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }
</style>
