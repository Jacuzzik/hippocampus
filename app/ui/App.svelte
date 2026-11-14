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
  import LoadingScreen from "./overlays/LoadingScreen.svelte";
  import HealthBar from "./overlays/HealthBar.svelte";
  import Notices from "./overlays/Notices.svelte";
  import PanelBoundary from "./controls/PanelBoundary.svelte";
  import { every } from "./poll.ts";
  import { bootTask, boot } from "./owner/bootTasks.svelte.ts";
  import ToolsDialog from "./overlays/ToolsDialog.svelte";
  import ControlDialog from "./control/ControlDialog.svelte";
  import AddAgentDialog from "./control/AddAgentDialog.svelte";
  import SettingsDialog from "./control/SettingsDialog.svelte";
  import CommandBox, { type Item } from "./overlays/CommandBox.svelte";
  import type { GraphData } from "./graph/model.ts";
  import { selection } from "./owner/addedAgents.svelte.ts";
  import { SETTINGS_PAGES, type SettingsPage } from "./control/model.ts";
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
  // The shell element, so a drag handle can set the sidebar and panel widths on it.
  let shell: HTMLDivElement | undefined = $state();

  /** Drag a side column's edge to resize it; the graph takes the rest. */
  function startResize(side: "left" | "right", event: PointerEvent): void {
    if (!shell) return;
    event.preventDefault(); // no text selection while dragging
    const column = side === "left" ? "--sidebar-col" : "--panel-col";
    const startX = event.clientX;
    const startWidth =
      (side === "left"
        ? shell.querySelector(".sidebar")
        : shell.querySelector(".right-panel")
      )?.getBoundingClientRect().width ?? 240;
    let width = startWidth;
    let frame: number | null = null;
    // Apply at most one width per animation frame, so the graph redraws once per frame, not per mouse move.
    const move = (e: PointerEvent): void => {
      const delta = side === "left" ? e.clientX - startX : startX - e.clientX;
      // The right panel never shrinks below its 500px default; the notes sidebar goes down to 160px.
      const min = side === "left" ? 160 : 500;
      width = Math.min(560, Math.max(min, startWidth + delta));
      frame ??= requestAnimationFrame(() => {
        frame = null;
        shell?.style.setProperty(column, `${width}px`);
      });
    };
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    const up = (): void => {
      if (frame !== null) cancelAnimationFrame(frame);
      shell?.style.setProperty(column, `${width}px`);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }
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
  let settingsStart = $state<SettingsPage>("General");
  // Full screen layout from the top bar: only the terminal and the agent cards show.
  let terminalOnly = $state(false);
  // Focus mode: with an agent selected, everything but its terminal and card dims. Escape leaves.
  let focusOn = $state(false);
  $effect(() => {
    if (selection.id === null) focusOn = false;
  });

  // Ctrl on Linux and Windows, Cmd on macOS. Both shortcuts take over the browser default.
  // F11 toggles full screen, as in browsers. Needs the window fullscreen permissions in capabilities.
  async function toggleFullscreen(): Promise<void> {
    const win = getCurrentWindow();
    await win.setFullscreen(!(await win.isFullscreen()));
  }

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape" && focusOn) {
      focusOn = false;
      return;
    }
    if (e.key === "F11" && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      void toggleFullscreen();
      return;
    }
    if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
    if (e.key === "o") box = "switcher";
    else if (e.key === "p") box = "palette";
    else if (e.key === "f") void focusSearch();
    else if (e.key === ",") {
      settingsStart = "General";
      settingsOpen = true;
    } else return;
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
      id: "focus",
      label: "Focus on the selected agent (Escape leaves)",
      run: () => (focusOn = selection.id !== null),
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
      run: () => {
        settingsStart = "General";
        settingsOpen = true;
      },
    },
    // One entry per Settings page, so the palette jumps straight to it.
    ...SETTINGS_PAGES.map((entry) => ({
      id: `settings-${entry.id}`,
      label: `Settings: ${entry.id}`,
      run: () => {
        settingsStart = entry.id;
        settingsOpen = true;
      },
    })),
  ];

  const noteItems = $derived<Item[]>(
    (data?.nodes ?? []).map((node) => ({
      id: node.id,
      label: node.title,
      hint: node.id,
      run: () => (selectedId = node.id),
    })),
  );

  // Reloads every few seconds so notes the agents add or change show up. The data is swapped only when
  // notes or links changed, so the graph layout does not reset on each poll.
  // The loading screen lifts after the first attempt, whether it worked or not.
  let booted = $state(false);

  async function load(): Promise<void> {
    try {
      const next = await invoke<GraphData>("sidecar_call", { method: "graph" });
      const changed =
        !data ||
        next.nodes.length !== data.nodes.length ||
        next.edges.length !== data.edges.length ||
        // Tags too: a colour change alters only the tags, and the colour is drawn from them.
        next.nodes.some(
          (node, i) =>
            node.id !== data?.nodes[i]?.id ||
            node.tags.join() !== data?.nodes[i]?.tags.join(),
        );
      if (changed) data = next;
      error = null;
    } catch (cause) {
      error = String(cause);
    } finally {
      booted = true;
    }
  }

  // The graph menu and sidebar fire this after a change, so it redraws at once rather than at the next poll.
  onMount(() => {
    // The first graph load (the vault) counts as start-up work; later polls do not.
    const doneVault = bootTask("Notes and graph");
    void load().finally(doneVault);
    const stopPoll = every(() => void load(), 5000);
    const onChanged = () => void load();
    window.addEventListener("graph-changed", onChanged);
    // TALK on a card needs the right panel on screen before its message box can take the cursor.
    const onTalk = () => (panelOpen = true);
    window.addEventListener("agent-talk", onTalk);
    // The graph reads its colours when it is created; a new theme needs a new graph.
    const onTheme = () => viewKey++;
    window.addEventListener("theme-changed", onTheme);
    // The spend meter in the status bar opens Settings on the page it names.
    const onOpenSettings = (event: Event) => {
      settingsStart = (event as CustomEvent<SettingsPage>).detail;
      settingsOpen = true;
    };
    window.addEventListener("open-settings", onOpenSettings);
    // The browser's own right-click menu is off everywhere; the app's own menus still open from their handlers.
    const noNativeMenu = (e: MouseEvent) => e.preventDefault();
    window.addEventListener("contextmenu", noNativeMenu);
    return () => {
      window.removeEventListener("contextmenu", noNativeMenu);
      window.removeEventListener("theme-changed", onTheme);
      window.removeEventListener("open-settings", onOpenSettings);
      stopPoll();
      window.removeEventListener("graph-changed", onChanged);
      window.removeEventListener("agent-talk", onTalk);
    };
  });
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
  <PanelBoundary name="Tools"
    ><ToolsDialog onclose={() => (toolsOpen = false)} /></PanelBoundary
  >
{/if}

{#if controlOpen}
  <PanelBoundary name="Control panel">
    <ControlDialog
      onclose={() => (controlOpen = false)}
      onsettings={() => {
        controlOpen = false;
        settingsOpen = true;
      }}
    />
  </PanelBoundary>
{/if}

{#if addOpen}
  <PanelBoundary name="Add agent"
    ><AddAgentDialog onclose={() => (addOpen = false)} /></PanelBoundary
  >
{/if}

{#if settingsOpen}
  <PanelBoundary name="Settings"
    ><SettingsDialog
      start={settingsStart}
      onclose={() => (settingsOpen = false)}
    /></PanelBoundary
  >
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

<LoadingScreen ready={booted && !boot.busy} />
<HealthBar
  backendDown={booted && error !== null && /sidecar|backend/i.test(error)}
/>
<Notices />

<div
  class="shell"
  bind:this={shell}
  class:no-sidebar={!sidebarOpen}
  class:no-panel={!panelOpen}
  class:terminal-only={terminalOnly}
  class:focus={focusOn}
>
  <Ribbon
    bind:sidebarOpen
    bind:panelOpen
    onaccount={() => (setupOpen = true)}
    oncontrol={() => (controlOpen = true)}
    onsettings={() => {
      settingsStart = "General";
      settingsOpen = true;
    }}
  />
  {#if sidebarOpen && data && !terminalOnly}
    <PanelBoundary name="Notes" area="sidebar">
      <NoteSidebar
        {data}
        bind:query
        bind:tag
        bind:memory
        bind:selectedId
        bind:searchEl
      />
    </PanelBoundary>
  {/if}
  <PanelBoundary name="Graph" area="graph">
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
  </PanelBoundary>
  <PanelBoundary name="Control Room" area="panel">
    <RightPanel open={panelOpen || terminalOnly} />
  </PanelBoundary>
  {#if sidebarOpen && data && !terminalOnly}
    <div
      class="resize-handle left"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize notes sidebar"
      onpointerdown={(e) => startResize("left", e)}
    ></div>
  {/if}
  {#if panelOpen || terminalOnly}
    <div
      class="resize-handle right"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize right panel"
      onpointerdown={(e) => startResize("right", e)}
    ></div>
  {/if}
  <StatusBar {data} onadd={() => (addOpen = true)} />
</div>

<style>
  .resize-handle {
    position: absolute;
    top: 0;
    bottom: var(--layout-status-bar-height);
    width: 6px;
    cursor: col-resize;
    z-index: 2;
  }
  .resize-handle.left {
    left: calc(var(--layout-ribbon-width) + var(--sidebar-col) - 3px);
  }
  .resize-handle.right {
    right: calc(var(--panel-col) - 3px);
  }
  .shell {
    position: relative;
    --sidebar-col: var(--layout-sidebar-width);
    --panel-col: 500px; /* the right panel's default width */
    --layout-status-bar-height: 136px;
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
      --panel-col: min(400px, 34vw);
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
  /* Focus mode: the notes and the graph step back; the right panel and the agent cards stay. */
  .shell > :global(.sidebar),
  .shell > :global(.graph),
  .shell > :global(.right-panel) {
    transition: opacity var(--duration-base) var(--ease-standard);
  }

  .shell.focus > :global(.sidebar),
  .shell.focus > :global(.graph) {
    opacity: 0.3;
  }

  .shell.focus :global(.chip:not(.selected)) {
    opacity: 0.4;
  }

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
