<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { getCurrentWindow } from "@tauri-apps/api/window";
  import { onMount } from "svelte";
  import GraphRegion from "./regions/GraphRegion.svelte";
  import NoteSidebar from "./regions/NoteSidebar.svelte";
  import Ribbon from "./regions/Ribbon.svelte";
  import RightPanel from "./regions/RightPanel.svelte";
  import StatusBar from "./regions/StatusBar.svelte";
  import AccountDialog from "./overlays/AccountDialog.svelte";
  import ToolsDialog from "./overlays/ToolsDialog.svelte";
  import ControlDialog from "./control/ControlDialog.svelte";
  import AddAgentDialog from "./control/AddAgentDialog.svelte";
  import SettingsDialog from "./control/SettingsDialog.svelte";
  import CommandBox, { type Item } from "./overlays/CommandBox.svelte";
  import type { GraphData } from "./graph/model.ts";
  import { tick } from "svelte";

  let data = $state<GraphData | null>(null);
  let error = $state<string | null>(null);
  let query = $state("");
  let tag = $state<string | null>(null);
  let memory = $state(false);
  let selectedId = $state<string | null>(null);
  // Phones and portrait tablets start with the note list and assistant closed, so the graph gets the screen.
  const narrow = window.matchMedia("(max-width: 900px)").matches;
  let sidebarOpen = $state(!narrow);
  let panelOpen = $state(!narrow);
  // Which overlay box is open: the quick switcher (Ctrl+O) or the command palette (Ctrl+P).
  let box = $state<"switcher" | "palette" | null>(null);
  let searchEl = $state<HTMLInputElement | null>(null);
  // Bumping this remounts the graph, which refits it to the canvas.
  let viewKey = $state(0);
  // Setup and account: opens on first run (no brain yet) and from the ribbon or the palette.
  let setupOpen = $state(false);
  // The assistant tool allowlist: from the command palette.
  let toolsOpen = $state(false);
  // The control panel: network, budgets, activity, questions, memory, jobs, helpers, sharing, skills, keys.
  let controlOpen = $state(false);
  let addOpen = $state(false);
  // The settings: six tabs, from the command palette or the control panel.
  let settingsOpen = $state(false);
  // Full screen layout from the top bar: only the terminal and the agent cards show.
  let terminalOnly = $state(false);

  // Ctrl on Linux and Windows, Cmd on macOS. Both shortcuts take over the browser default.
  // F11 toggles full screen, as in browsers. Needs the window fullscreen permissions in capabilities.
  async function toggleFullscreen(): Promise<void> {
    const win = getCurrentWindow();
    await win.setFullscreen(!(await win.isFullscreen()));
  }

  function onKey(e: KeyboardEvent): void {
    if (e.key === "F11" && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      void toggleFullscreen();
      return;
    }
    if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
    if (e.key === "o") box = "switcher";
    else if (e.key === "p") box = "palette";
    else if (e.key === "f") void focusSearch();
    else return;
    e.preventDefault();
  }

  async function focusSearch(): Promise<void> {
    box = null;
    sidebarOpen = true;
    await tick();
    searchEl?.focus();
    searchEl?.select();
  }

  const commands: Item[] = [
    {
      id: "toggle-sidebar",
      label: "Toggle note list",
      run: () => (sidebarOpen = !sidebarOpen),
    },
    {
      id: "toggle-assistant",
      label: "Toggle assistant",
      run: () => (panelOpen = !panelOpen),
    },
    { id: "search", label: "Search notes", run: focusSearch },
    {
      id: "fullscreen",
      label: "Toggle full screen (F11)",
      run: toggleFullscreen,
    },
    {
      id: "reset-graph",
      label: "Reset graph view",
      run: () => viewKey++,
    },
    {
      id: "account",
      label: "Setup and account",
      run: () => (setupOpen = true),
    },
    {
      id: "tools",
      label: "Assistant tools",
      run: () => (toolsOpen = true),
    },
    {
      id: "control",
      label: "Control panel",
      run: () => (controlOpen = true),
    },
    {
      id: "settings",
      label: "Settings",
      run: () => (settingsOpen = true),
    },
  ];

  const noteItems = $derived<Item[]>(
    (data?.nodes ?? []).map((node) => ({
      id: node.id,
      label: node.title,
      hint: node.id,
      run: () => (selectedId = node.id),
    })),
  );

  async function load(): Promise<void> {
    try {
      data = await invoke<GraphData>("sidecar_call", { method: "graph" });
      error = null;
    } catch (cause) {
      // Without a brain the graph cannot load, so the setup opens to choose one.
      error = String(cause);
      setupOpen = true;
    }
  }

  onMount(load);
</script>

<svelte:window onkeydown={onKey} />

{#if box === "palette"}
  <CommandBox
    items={commands}
    placeholder="Type a command"
    label="Command palette"
    onclose={() => (box = null)}
  />
{:else if box === "switcher"}
  <CommandBox
    items={noteItems}
    placeholder="Open a note by name"
    label="Quick switcher"
    onclose={() => (box = null)}
  />
{/if}

{#if toolsOpen}
  <ToolsDialog onclose={() => (toolsOpen = false)} />
{/if}

{#if controlOpen}
  <ControlDialog
    onclose={() => (controlOpen = false)}
    onsettings={() => {
      controlOpen = false;
      settingsOpen = true;
    }}
  />
{/if}

{#if addOpen}
  <AddAgentDialog onclose={() => (addOpen = false)} />
{/if}

{#if settingsOpen}
  <SettingsDialog onclose={() => (settingsOpen = false)} />
{/if}

{#if setupOpen}
  <AccountDialog
    onclose={() => (setupOpen = false)}
    onopened={() => {
      error = null;
      void load();
    }}
  />
{/if}

<div
  class="shell"
  class:no-sidebar={!sidebarOpen}
  class:no-panel={!panelOpen}
  class:terminal-only={terminalOnly}
>
  <Ribbon
    bind:sidebarOpen
    bind:panelOpen
    onaccount={() => (setupOpen = true)}
    oncontrol={() => (controlOpen = true)}
  />
  {#if sidebarOpen && data && !terminalOnly}
    <NoteSidebar
      {data}
      bind:query
      bind:tag
      bind:memory
      bind:selectedId
      bind:searchEl
    />
  {/if}
  <GraphRegion
    {data}
    {error}
    {query}
    {tag}
    {memory}
    {selectedId}
    {viewKey}
    fullscreen={terminalOnly}
    onfullscreen={() => (terminalOnly = !terminalOnly)}
    onselect={(id) => (selectedId = id)}
  />
  <RightPanel open={panelOpen || terminalOnly} />
  <StatusBar {data} onadd={() => (addOpen = true)} />
</div>

<style>
  .shell {
    --sidebar-col: var(--layout-sidebar-width);
    --panel-col: var(--layout-right-panel-width);
    --layout-status-bar-height: 72px;
    display: grid;
    grid-template-columns:
      var(--layout-ribbon-width) var(--sidebar-col) minmax(0, 1fr)
      var(--panel-col);
    grid-template-rows: minmax(0, 1fr) var(--layout-status-bar-height);
    grid-template-areas:
      "rail sidebar graph panel"
      "status status status status";
    height: 100%;
    overflow: hidden;
  }

  /* Narrow windows (960px wide) keep the graph readable: the panels yield width first. */
  @media (max-width: 1100px) {
    .shell {
      --sidebar-col: 200px;
      --panel-col: min(var(--layout-right-panel-width), 34vw);
    }
  }

  /* Tablets and phones: the rail grows to a 44px touch target. */
  @media (max-width: 1100px) {
    .shell {
      --layout-ribbon-width: 60px;
    }
  }

  /* Phones and portrait tablets: the graph takes the screen, and the note list and assistant
     open over it as drawers. */
  @media (max-width: 900px) {
    .shell {
      grid-template-columns: var(--layout-ribbon-width) minmax(0, 1fr);
      grid-template-areas:
        "rail graph"
        "status status";
    }

    .shell > :global(.sidebar),
    .shell > :global(.right-panel) {
      position: fixed;
      top: 0;
      bottom: var(--layout-status-bar-height);
      left: var(--layout-ribbon-width);
      z-index: 5;
      grid-area: auto;
      max-width: calc(100vw - var(--layout-ribbon-width));
      box-shadow: var(--layout-drawer-shadow);
    }

    .shell > :global(.sidebar) {
      width: min(
        var(--layout-sidebar-width),
        100vw - var(--layout-ribbon-width)
      );
    }

    .shell > :global(.right-panel) {
      right: 0;
      width: auto;
    }
  }

  .shell.no-sidebar {
    --sidebar-col: 0px;
  }

  .shell.no-panel {
    --panel-col: 0px;
  }

  /* Full screen layout: the graph column shrinks to its top bar, the terminal takes the rest. */
  .shell.terminal-only {
    grid-template-columns: var(--layout-ribbon-width) auto minmax(0, 1fr);
    grid-template-areas:
      "rail graph panel"
      "status status status";
  }

  /* The graph's status notice spans the whole graph area, which includes the note drawer beside it;
     let clicks and wheel reach the drawer. shortcut: fix the notice rule in ui/graph/BrainGraph.svelte. */
  :global(.brain > .notice) {
    pointer-events: none;
  }
</style>
