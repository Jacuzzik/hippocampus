<script lang="ts">
  // The dashboards: a full-window view with a list of dashboards on the left and tiles on the right.
  // Numbers are read when a dashboard opens and when Refresh is pressed, never on a timer.
  // Locked (Settings > Dashboards) makes the tiles read-only: no click, no typing, no keyboard focus.
  import { invoke } from "@tauri-apps/api/core";
  import { dialogFocus } from "../controls/dialogFocus.ts";
  import ErrorRow from "../controls/ErrorRow.svelte";
  import Loading from "../controls/Loading.svelte";
  import Tabs from "../controls/Tabs.svelte";
  import { prefs } from "../prefs.svelte.ts";
  import {
    activityTiles,
    DASHBOARDS,
    noteTiles,
    overviewTiles,
    spendTiles,
    systemTiles,
    taskTiles,
    type ActivityRow,
    type DashboardId,
    type GraphShape,
    type SystemShape,
    type TaskRow,
    type Tile,
  } from "./model.ts";

  let { onclose, onsettings }: { onclose: () => void; onsettings: () => void } =
    $props();

  let current = $state<DashboardId>("overview");
  let tiles = $state<Tile[] | null>(null);
  let error = $state<string | null>(null);
  let readAt = $state("");

  const call = <T,>(method: string): Promise<T> =>
    invoke<T>("sidecar_call", { method });
  const spend = async (): Promise<Record<string, number>> =>
    (await call<{ by_agent?: Record<string, number> }>("budget")).by_agent ??
    {};
  const tasks = async (): Promise<TaskRow[]> =>
    (await call<{ tasks: TaskRow[] }>("tasks")).tasks;

  // What each dashboard reads. One that fails shows its reason and a Try again button.
  const READERS: Record<DashboardId, () => Promise<Tile[]>> = {
    overview: async () => {
      const [agents, used, cards, asks, system] = await Promise.all([
        call<{ agents: unknown[] }>("agents"),
        spend(),
        tasks(),
        call<{ asks: unknown[] }>("asks"),
        call<SystemShape>("system").catch(() => null),
      ]);
      return overviewTiles({
        agents: agents.agents.length,
        tokens: Object.values(used).reduce((sum, n) => sum + n, 0),
        tasks: cards,
        asks: asks.asks.length,
        system,
      });
    },
    agents: async () => spendTiles(await spend()),
    tasks: async () => taskTiles(await tasks()),
    notes: async () => noteTiles(await call<GraphShape>("graph")),
    system: async () => systemTiles(await call<SystemShape>("system")),
    activity: async () =>
      activityTiles((await call<{ rows: ActivityRow[] }>("activity")).rows),
  };

  async function load(): Promise<void> {
    const wanted = current;
    tiles = null;
    error = null;
    try {
      const found = await READERS[wanted]();
      if (wanted !== current) return; // the user moved on while it was read
      tiles = found;
      readAt = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (cause) {
      if (wanted === current) error = String(cause);
    }
  }
  $effect(() => {
    void current;
    void load();
  });

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }
  const title = $derived(
    DASHBOARDS.find((item) => item.id === current)?.label ?? "",
  );
</script>

<div
  class="view"
  role="dialog"
  aria-modal="true"
  aria-label="Dashboards"
  tabindex="-1"
  use:dialogFocus
  onkeydown={onKey}
>
  <header>
    <h2>Dashboards</h2>
    <button
      type="button"
      class="lock"
      class:on={prefs.dashboardsLocked}
      aria-label={prefs.dashboardsLocked
        ? "Dashboards are locked. Open the lock setting"
        : "Dashboards are unlocked. Open the lock setting"}
      onclick={onsettings}
      >{prefs.dashboardsLocked ? "Locked" : "Unlocked"}</button
    >
    <span class="read" role="status">{readAt ? `Read at ${readAt}` : ""}</span>
    <button type="button" onclick={() => void load()}>Refresh</button>
    <button
      type="button"
      class="close"
      aria-label="Close dashboards"
      onclick={onclose}>×</button
    >
  </header>
  <div class="body">
    <nav>
      <Tabs
        items={DASHBOARDS.map((item) => ({ id: item.id, label: item.label }))}
        bind:value={current}
        label="Dashboards"
        idBase="dashboards"
        vertical
      />
    </nav>
    <div
      class="board"
      role="tabpanel"
      aria-label={title}
      inert={prefs.dashboardsLocked}
      class:locked={prefs.dashboardsLocked}
    >
      <h3>{title}</h3>
      {#if error}
        <ErrorRow message={error} onretry={() => void load()} />
      {:else if tiles === null}
        <Loading what={title} />
      {:else}
        <ul class="tiles">
          {#each tiles as tile (tile.label)}
            <li class:warn={tile.tone === "warn"}>
              <span class="label">{tile.label}</span>
              <b>{tile.value}</b>
              {#if tile.note}<span class="note">{tile.note}</span>{/if}
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </div>
</div>

<style>
  .view {
    position: fixed;
    inset: 0;
    z-index: 15;
    display: flex;
    flex-direction: column;
    padding: var(--space-4);
    color: var(--color-text);
    background: var(--color-bg-0);
  }

  header {
    display: flex;
    gap: var(--space-3);
    align-items: center;
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--color-border);
  }

  h2,
  h3 {
    margin: 0;
    font-size: var(--font-size-lg);
  }

  header button {
    min-height: var(--size-28);
    padding: var(--space-1) var(--space-3);
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  header .lock.on {
    color: var(--color-accent-on);
    background: var(--color-accent);
    border-color: var(--color-accent);
  }

  .read {
    margin-left: auto;
    color: var(--color-text-muted);
  }

  header .close {
    min-width: var(--size-28);
    padding: 0 var(--space-2);
    color: var(--color-text-muted);
    font-size: var(--font-size-lg);
    background: none;
    border: 0;
  }

  .body {
    display: grid;
    grid-template-columns: 220px minmax(0, 1fr);
    gap: var(--space-4);
    flex: 1;
    min-height: 0;
    padding-top: var(--space-3);
  }

  nav {
    overflow-y: auto;
  }

  .board {
    min-width: 0;
    overflow-y: auto;
  }

  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: var(--space-3);
    margin: var(--space-3) 0 0;
    padding: 0;
    list-style: none;
  }

  .tiles li {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 0;
    padding: var(--space-3);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .tiles li.warn {
    border-left-color: var(--color-danger);
  }

  .label,
  .note {
    color: var(--color-text-muted);
    overflow-wrap: anywhere;
  }

  .tiles b {
    font-size: var(--font-size-lg);
    overflow-wrap: anywhere;
  }
</style>
