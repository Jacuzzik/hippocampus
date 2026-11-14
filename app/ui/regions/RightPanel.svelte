<script lang="ts">
  import { FONT_MAX, FONT_MIN, prefs } from "../prefs.svelte.ts";
  import { every } from "../poll.ts";
  import { onMount, tick } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import Assistant from "../assistant/Assistant.svelte";
  import Tabs, { type TabItem } from "../controls/Tabs.svelte";
  import { createTerminalQueue } from "./terminalQueue.svelte";

  // The main agent's terminal runs the provider saved in the engine switch (CLI name is the provider id).
  let mainProvider = $state("claude");
  // Bumped when the engine changes, so the terminal panel remounts and starts the new provider.
  let terminalKey = $state(0);
  // remount: only the first load remounts the terminal. A model switch already restarts it inside LiveTerminal,
  // so a remount here would destroy the switch popup and start a second session.
  function loadEngine(remount = false): void {
    invoke<{ provider: string }>("sidecar_call", { method: "engine" })
      .then((value) => {
        mainProvider = value.provider;
        if (remount) terminalKey += 1;
      })
      .catch(() => (mainProvider = "claude"));
  }
  // The main agent's real terminal state from the sidecar: running while its CLI is up, otherwise idle.
  let hippoInfo = $state<{ command: string | null; status: string | null }>({
    command: null,
    status: null,
  });
  // What the terminal itself last reported: null until its program has started.
  let screenState = $state<{
    state: TerminalState;
    code: number | null;
  } | null>(null);
  // One word for the terminal: starting, then running (its program is working) or idle (waiting for you);
  // stopped when it was closed on purpose or ended cleanly, crashed when it ended with an error.
  const hippoState = $derived.by(() => {
    if (!screenState) return "starting";
    if (screenState.state === "failed") return "could not start";
    if (screenState.state === "stopped") return "stopped";
    if (screenState.state === "exited")
      return screenState.code ? "crashed" : "stopped";
    return hippoInfo.command ? "running" : "idle";
  });
  function readHippo(): void {
    invoke<{ command: string | null; status: string | null }>("sidecar_call", {
      method: "terminal_command",
      params: { agent: "hippoherman" },
    })
      .then(
        (value) =>
          (hippoInfo = { command: value.command, status: value.status }),
      )
      .catch(() => (hippoInfo = { command: null, status: null }));
  }
  onMount(() => {
    loadEngine(true);
    readHippo();
    const stopPoll = every(readHippo, 3000);
    readCounts();
    const stopCounts = every(readCounts, 10000);
    const onEngineChanged = () => loadEngine(false);
    window.addEventListener("engine-changed", onEngineChanged);
    window.addEventListener("agent-talk", onTalk);
    return () => {
      window.removeEventListener("agent-talk", onTalk);
      stopPoll();
      stopCounts();
      window.removeEventListener("engine-changed", onEngineChanged);
    };
  });
  import TasksPanel from "./TasksPanel.svelte";
  import InboxPanel from "./InboxPanel.svelte";
  import MemoryPanel from "./MemoryPanel.svelte";
  import MonitorPanel from "./MonitorPanel.svelte";
  import AsksSection from "../control/AsksSection.svelte";
  import TriggersSection from "../control/TriggersSection.svelte";
  import ActivityPanel from "./ActivityPanel.svelte";
  import SkillsPanel from "./SkillsPanel.svelte";
  import TempsPanel from "./TempsPanel.svelte";
  import HistoryPanel from "./HistoryPanel.svelte";
  import AgentPanel from "../owner/AgentPanel.svelte";
  import LiveTerminal, { type TerminalState } from "./LiveTerminal.svelte";
  import {
    addedAgents,
    archived,
    selectAgent,
    selection,
  } from "../owner/addedAgents.svelte";

  // Kept mounted when hidden so the chat session and its tool log survive a toggle.
  let { open = true }: { open?: boolean } = $props();

  // The selected added agent (a card click). Its own tab shows while it is selected.
  const agent = $derived(
    addedAgents.list.find(
      (a) => a.id === selection.id && !archived.ids.includes(a.id),
    ) ?? null,
  );

  // Names match the office app's Command Center tabs. The terminal is mounted at launch; the other views mount
  // the first time they are opened and then stay (see `visited`).
  const TABS = [
    "terminal",
    "monitor",
    "tasks",
    "inbox",
    "ask me",
    "triggers",
    "history",
    "memory",
    "activity",
    "skills",
    "temps",
  ];
  const VIEWS = TABS.filter((id) => id !== "terminal");
  let visited = $state<string[]>([]);
  $effect(() => {
    if (VIEWS.includes(tab) && !visited.includes(tab))
      visited = [...visited, tab];
  });
  // Counts shown on the tabs: questions waiting for an answer, and inbox messages not handled yet.
  let waiting = $state({ asks: 0, inbox: 0 });
  function readCounts(): void {
    invoke<{ asks: unknown[] }>("sidecar_call", { method: "asks" })
      .then((value) => (waiting.asks = value.asks.length))
      .catch(() => {});
    invoke<{ messages: { state: string }[] }>("sidecar_call", {
      method: "inbox",
    })
      .then(
        (value) =>
          (waiting.inbox = value.messages.filter(
            (m) => m.state === "queued",
          ).length),
      )
      .catch(() => {});
  }
  // The views sit in rows of four, as in the picture. A selected agent adds its own tab at the end.
  const tabItems = $derived<TabItem[]>([
    ...TABS.map((id) => ({
      id,
      label: id,
      badge:
        id === "ask me"
          ? waiting.asks
          : id === "inbox"
            ? waiting.inbox
            : undefined,
    })),
    ...(agent ? [{ id: "agent", label: agent.name }] : []),
  ]);
  // Opens on the tab used last, when that setting is on (Settings > General).
  let tab = $state(
    prefs.rememberTab && TABS.includes(prefs.lastTab)
      ? prefs.lastTab
      : "terminal",
  );
  $effect(() => {
    if (tab !== "agent") prefs.lastTab = tab;
  });
  const fontSize = $derived(prefs.terminalFontSize);

  // The Control Room message box sends into Hippo's terminal, through a queue (see terminalQueue).
  const queue = createTerminalQueue(() => "hippoherman");
  $effect(() => {
    const timer = setInterval(queue.tick, 1000);
    return () => clearInterval(timer);
  });

  // A card's TALK button: show that agent's terminal and put the cursor in its message box.
  let panel: HTMLDivElement | undefined = $state();
  function onTalk(event: Event): void {
    const id = (event as CustomEvent<string>).detail;
    if (id === "hippoherman") {
      selectAgent(null);
      tab = "terminal";
    } else {
      selectAgent(id);
    }
    void tick().then(() => {
      // The terminal keeps a hidden textarea of its own for typing; the message box is the other one.
      for (const box of panel?.querySelectorAll<HTMLTextAreaElement>(
        "textarea:not(.xterm-helper-textarea)",
      ) ?? []) {
        if (box.offsetParent !== null) {
          box.focus();
          break;
        }
      }
    });
  }

  // Selecting a card opens its tab; deselecting (or archiving or deleting it) returns to the terminal.
  $effect(() => {
    if (agent) tab = "agent";
    else if (tab === "agent") tab = "terminal";
  });
</script>

<div class="right-panel" hidden={!open} bind:this={panel}>
  <div class="column">
    {#if !(tab === "agent" && agent)}
      <div class="title">
        <b>Control Room</b><span class="pill">■ Live</span>
      </div>
      <div class="card">
        <Tabs
          items={tabItems}
          bind:value={tab}
          label="Panels"
          idBase="control-room"
          segmented
          columns={4}
        />
      </div>
    {/if}
    <div
      class="pane"
      id={tab === "terminal" ? "control-room-panel" : undefined}
      hidden={tab !== "terminal"}
    >
      <div class="live">
        <span
          class="dot"
          class:bad={hippoState === "crashed" ||
            hippoState === "could not start"}
          class:off={hippoState === "stopped" || hippoState === "starting"}
          aria-hidden="true"
        ></span>
        <!-- A screen reader hears the terminal start or stop: this is the one live region for its state. -->
        <span role="status" aria-label="Terminal state">{hippoState}</span>
        <span class="size">
          <button
            type="button"
            aria-label="Smaller text"
            disabled={fontSize <= FONT_MIN}
            onclick={() => (prefs.terminalFontSize -= 1)}>−</button
          >
          <output>{fontSize}px</output>
          <button
            type="button"
            aria-label="Larger text"
            disabled={fontSize >= FONT_MAX}
            onclick={() => (prefs.terminalFontSize += 1)}>+</button
          >
        </span>
      </div>
      <div class="live-wrap">
        {#key terminalKey}
          <LiveTerminal
            agentId="hippoherman"
            provider={mainProvider}
            {fontSize}
            followEngine
            onoutput={queue.output}
            onstate={(state, code) => (screenState = { state, code })}
          />
        {/key}
      </div>
      <Assistant onsend={queue.send} queued={queue.items} />
    </div>
    <!-- Kept mounted while other tabs are open, so its terminal and listeners survive a tab switch. -->
    <!-- Every agent's panel is mounted at launch so its terminal starts in the background (kept hidden when not shown). -->
    {#each addedAgents.list.filter((a) => !archived.ids.includes(a.id)) as item (item.id)}
      <div class="pane" hidden={tab !== "agent" || selection.id !== item.id}>
        <AgentPanel agent={item} />
      </div>
    {/each}
    <!-- A tab opened once stays mounted (hidden) so a switch does not reload its list or lose its scroll. -->
    {#each VIEWS as view (view)}
      {#if visited.includes(view)}
        <div
          class="pane"
          id={tab === view ? "control-room-panel" : undefined}
          role="tabpanel"
          aria-labelledby={`control-room-tab-${view.replace(/\W+/g, "-")}`}
          hidden={tab !== view}
        >
          {#if view === "tasks"}
            <TasksPanel />
          {:else if view === "inbox"}
            <InboxPanel />
          {:else if view === "memory"}
            <MemoryPanel />
          {:else if view === "monitor"}
            <MonitorPanel />
          {:else if view === "ask me"}
            <AsksSection />
          {:else if view === "triggers"}
            <TriggersSection />
          {:else if view === "activity"}
            <ActivityPanel />
          {:else if view === "skills"}
            <SkillsPanel />
          {:else if view === "temps"}
            <TempsPanel />
          {:else if view === "history"}
            <HistoryPanel />
          {/if}
        </div>
      {/if}
    {/each}
  </div>
</div>

<style>
  .right-panel {
    grid-area: panel;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }

  .right-panel[hidden] {
    display: none;
  }

  /* The dark terminal box from the mockup: the assistant's chat sits inside it. */
  .column {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    margin: var(--space-2);
    padding: var(--space-2);
    background: var(--color-bg-0);
    border-radius: var(--radius-md);
    font-family: var(--font-ui);
  }

  .live {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--font-size-xs);
    color: var(--color-md-text-muted);
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-md-accent);
  }

  .dot.bad {
    background: var(--color-danger);
  }

  .dot.off {
    background: var(--color-md-text-subtle);
  }

  .size {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  /* The size control is one segmented pill: − | 12px | +. */
  .size {
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  .size button {
    min-width: 36px;
    min-height: 32px;
    font: inherit;
    padding: 0;
    border: none;
    border-radius: 0;
    background: transparent;
    color: var(--color-md-text-muted);
    cursor: pointer;
  }

  .size output {
    min-width: 48px;
    text-align: center;
    border-left: 1px solid var(--color-md-border);
    border-right: 1px solid var(--color-md-border);
    color: var(--color-md-text-muted);
  }

  /* The orb status shows as a pill at the top of the panel, as in the mockup. */
  .column :global(.assistant .head) {
    display: inline-flex;
    align-self: flex-start;
    align-items: center;
    gap: var(--space-1);
    padding: 2px var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text);
    font-size: var(--font-size-tag);
  }

  .pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  /* The real terminal takes a fixed slice above the chat. */
  .live-wrap {
    flex: 1 1 0;
    min-height: 300px;
    display: flex;
    flex-direction: column;
    margin-bottom: var(--space-2);
  }

  .pane[hidden] {
    display: none;
  }

  /* Control Room cards: views, session and terminal status, and the queue, each in its own bordered card. */
  .title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--space-2);
  }
  .title b {
    font-size: var(--font-size-md);
    letter-spacing: 0.04em;
  }
  .pill {
    padding: 2px var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    color: var(--color-md-text-muted);
    font-size: var(--font-size-tag);
  }
  /* No box around the title, views and live row: the mockup has bare rows. */
  .card {
    margin-bottom: var(--space-2);
  }
  /* Mockup match: the terminal sits in a bordered black box, the queue label is capitals, the buttons stay on one row. */
  .pane > :global(.assistant) :global(.term) {
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-bg-0);
  }
  /* Message box: same tokens, radius and size as the normal agent's. */
  .pane > :global(.assistant) :global(textarea) {
    min-height: 64px;
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text);
    font-size: var(--font-size-xs);
  }
  .pane > :global(.assistant) :global(.queue-label) {
    text-transform: uppercase;
  }
  .pane > :global(.assistant) :global(.composer .actions) {
    flex-wrap: nowrap;
    white-space: nowrap;
  }
  /* Queue, message box, Send bar and attachment pills: as in the mockup, no card around them. */
  .pane > :global(.assistant) > :global(.composer) {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: 0;
    border: none;
    background: none;
  }
  .pane > :global(.assistant) :global(.composer .send) {
    width: 100%;
    min-height: 32px;
    border: 1px solid var(--color-md-accent);
    border-radius: var(--radius-sm);
    background: var(--color-md-accent);
    color: var(--color-md-accent-on);
  }
  .pane > :global(.assistant) :global(.composer .attach) {
    display: flex;
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }
  .pane > :global(.assistant) :global(.composer .attach > button) {
    flex: 1;
    min-height: 32px;
    border: none;
    border-right: 1px solid var(--color-md-border);
    border-radius: 0;
    background: transparent;
    color: var(--color-md-text-muted);
  }
  .pane > :global(.assistant) :global(.composer .attach > button:last-child) {
    border-right: none;
  }
  /* Send and attachment buttons: same font and padding as the normal agent's. */
  .pane > :global(.assistant) :global(.composer button) {
    font: inherit;
    font-size: var(--font-size-xs);
    padding: 0 var(--space-2);
  }
  .pane > :global(.assistant) :global(.composer .stop) {
    border-radius: var(--radius-sm);
  }

  /* The chat takes only the space it needs, so the terminal above gets the rest, as on the normal agent. */
  .pane > :global(.assistant) {
    background: transparent;
    border-left: none;
    padding: 0;
    flex: 0 1 auto;
    min-height: 0;
    min-width: 0;
  }
</style>
