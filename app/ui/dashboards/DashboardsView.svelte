<script lang="ts">
  import Button from "../controls/Button.svelte";
  // The dashboards: a full-window view with a list of dashboards on the left and tiles on the right.
  // Numbers are read when a dashboard opens and when Refresh is pressed, never on a timer.
  // Locked (Settings > Dashboards) makes the tiles read-only: no click, no typing, no keyboard focus.
  import { invoke } from "@tauri-apps/api/core";
  import { SvelteMap } from "svelte/reactivity";
  import ErrorRow from "../controls/ErrorRow.svelte";
  import Loading from "../controls/Loading.svelte";
  import DashIcon from "./DashIcon.svelte";
  import CalendarBoard from "./CalendarBoard.svelte";
  import PhoneBoard from "./PhoneBoard.svelte";
  import AnalyticPanel from "./AnalyticPanel.svelte";
  import { prefs } from "../prefs.svelte.ts";
  import {
    activityByDay,
    short,
    activityTiles,
    breakdown,
    heatValues,
    percentOf,
    type Panel,
    appTiles,
    DASHBOARDS,
    githubTiles,
    noteTiles,
    overviewTiles,
    spendTiles,
    systemTiles,
    taskTiles,
    type ActivityRow,
    type AppNumber,
    type DashboardId,
    type GithubShape,
    type GraphShape,
    type SystemShape,
    type TaskRow,
    type Tile,
  } from "./model.ts";

  let { onclose, onsettings }: { onclose: () => void; onsettings: () => void } =
    $props();

  // A built-in dashboard's id, or "app:<id>" for a connected app.
  let current = $state<string>("overview");
  // The connected apps: each one gets a dashboard after the built-in ones.
  let apps = $state<{ id: string; name: string }[]>([]);
  async function readApps(): Promise<void> {
    try {
      const found = await invoke<{
        apps: { id: string; name: string; connected: boolean }[];
      }>("sidecar_call", { method: "apps" });
      apps = found.apps.filter((app) => app.connected);
      if (
        current.startsWith("app:") &&
        !apps.some((a) => `app:${a.id}` === current)
      )
        current = "overview";
    } catch (cause) {
      console.error("Could not read the connected apps", cause);
    }
  }
  $effect(() => {
    void readApps();
    const again = () => void readApps();
    window.addEventListener("apps-changed", again);
    return () => window.removeEventListener("apps-changed", again);
  });
  const items = $derived([
    ...DASHBOARDS.map((item) => ({ id: item.id as string, label: item.label })),
    ...apps.map((app) => ({ id: `app:${app.id}`, label: app.name })),
  ]);
  let tiles = $state<Tile[] | null>(null);
  // Charts and breakdowns drawn above the tiles, set by the dashboard that reads them.
  let panels = $state<Panel[]>([]);
  let error = $state<string | null>(null);
  let readAt = $state("");
  // Bumped by Refresh, so a dashboard that loads itself reads again.
  let refreshed = $state(0);

  const call = <T,>(method: string): Promise<T> =>
    invoke<T>("sidecar_call", { method });
  const spend = async (): Promise<Record<string, number>> =>
    (await call<{ by_agent?: Record<string, number> }>("budget")).by_agent ??
    {};
  const tasks = async (): Promise<TaskRow[]> =>
    (await call<{ tasks: TaskRow[] }>("tasks")).tasks;

  // The GitHub dashboard needs a repository first; its field is part of the board, so the lock covers it.
  let repoDraft = $state(prefs.dashboardRepo);
  function saveRepo(event: SubmitEvent): void {
    event.preventDefault();
    prefs.dashboardRepo = repoDraft;
    void load();
  }
  const NEEDS_REPO = "Choose a repository first.";

  // What each dashboard reads. One that fails shows its reason and a Try again button.
  const READERS: Partial<Record<DashboardId, () => Promise<Tile[]>>> = {
    overview: async () => {
      const [agents, used, cards, asks, system, activity] = await Promise.all([
        call<{ agents: unknown[] }>("agents"),
        spend(),
        tasks(),
        call<{ asks: unknown[] }>("asks"),
        call<SystemShape>("system").catch(() => null),
        call<{ rows: ActivityRow[] }>("activity")
          .then((found) => found.rows)
          .catch(() => null),
      ]);
      const next: Panel[] = [];
      if (system)
        next.push({
          kind: "rings",
          title: "Machine",
          note: "Share of the machine in use now.",
          rings: [
            { label: "CPU", percent: system.cpu, warn: system.cpu >= 90 },
            { label: "RAM", percent: system.ram, warn: system.ram >= 90 },
          ],
        });
      if (cards.length)
        next.push({
          kind: "breakdown",
          title: "Tasks by status",
          note: `${cards.length} in all.`,
          rows: breakdown(
            ["todo", "doing", "blocked", "done"].map(
              (status) =>
                [
                  status.charAt(0).toUpperCase() + status.slice(1),
                  cards.filter((task) => task.status === status).length,
                  status === "blocked" &&
                    cards.some((task) => task.status === status),
                ] as [string, number, boolean],
            ),
          ),
        });
      if (activity) {
        const days = activityByDay(activity);
        next.push({
          kind: "trend",
          title: "Events per day",
          note: "Last 14 days",
          labels: days.labels,
          values: days.values,
        });
      }
      panels = next;
      return overviewTiles({
        // The main agent is always on the floor; the list holds only the agents added beside it.
        agents: agents.agents.length + 1,
        tokens: Object.values(used).reduce((sum, n) => sum + n, 0),
        tasks: cards,
        asks: asks.asks.length,
        system,
      });
    },
    agents: async () => {
      const byAgent = await spend();
      const rows = Object.entries(byAgent).sort((a, b) => b[1] - a[1]);
      panels = [
        {
          kind: "breakdown",
          title: "Tokens by agent",
          note: "Today's share of all tokens.",
          rows: breakdown(rows, short),
        },
      ];
      return spendTiles(byAgent);
    },
    tasks: async () => {
      const found = await tasks();
      const columns = ["todo", "doing", "blocked", "done"].map(
        (status) =>
          [
            status.charAt(0).toUpperCase() + status.slice(1),
            found.filter((task) => task.status === status).length,
          ] as [string, number],
      );
      panels = [
        {
          kind: "breakdown",
          title: "Tasks by status",
          note: `${found.length} in all.`,
          rows: breakdown(columns),
        },
      ];
      return taskTiles(found);
    },
    notes: async () => {
      const graph = await call<GraphShape>("graph");
      const counts = new SvelteMap<string, number>();
      for (const node of graph.nodes)
        for (const tag of node.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
      const top = [...counts.entries()]
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, 8);
      panels = top.length
        ? [
            {
              kind: "breakdown",
              title: "Top tags",
              note: "Notes that carry each tag.",
              rows: breakdown(top),
            },
          ]
        : [];
      return noteTiles(graph);
    },
    system: async () => {
      const system = await call<SystemShape>("system");
      panels = [
        {
          kind: "rings",
          title: "Machine",
          note: "Share of each resource in use now.",
          rings: [
            { label: "CPU", percent: system.cpu, warn: system.cpu >= 90 },
            { label: "RAM", percent: system.ram, warn: system.ram >= 90 },
            { label: "Swap", percent: system.swap, warn: system.swap >= 50 },
            { label: "Disk", percent: system.disk, warn: system.disk >= 90 },
          ],
        },
      ];
      return systemTiles(system);
    },
    github: async () => {
      if (!prefs.dashboardRepo) throw new Error(NEEDS_REPO);
      const found = await invoke<GithubShape | { error: string }>(
        "sidecar_call",
        { method: "github_board", params: { repo: prefs.dashboardRepo } },
      );
      if ("error" in found) throw new Error(found.error);
      const runs = found.runs;
      const passed = Math.max(0, runs - found.failed_runs - found.running_runs);
      const open = Math.max(0, found.pulls - found.drafts);
      panels = [
        {
          kind: "breakdown",
          title: "Recent CI runs",
          note: `${runs} read.`,
          rows: breakdown(
            [
              ["Passed", passed],
              ["Failed", found.failed_runs, found.failed_runs > 0],
              ["Running", found.running_runs],
            ] as [string, number, boolean?][],
          ),
        },
        {
          kind: "breakdown",
          title: "Pull requests",
          note: `${found.pulls} open.`,
          rows: breakdown([
            ["Ready", open],
            ["Drafts", found.drafts],
          ]),
        },
      ];
      return githubTiles(found);
    },
    activity: async () => {
      const rows = (await call<{ rows: ActivityRow[] }>("activity")).rows;
      const days = activityByDay(rows);
      panels = [
        {
          kind: "trend",
          title: "Events per day",
          note: "Last 14 days",
          labels: days.labels,
          values: days.values,
        },
        {
          kind: "heat",
          title: "Activity, 13 weeks",
          note: "Each square is one day.",
          values: heatValues(rows),
        },
      ];
      return activityTiles(rows);
    },
  };

  async function load(): Promise<void> {
    const wanted = current;
    tiles = null;
    panels = [];
    error = null;
    try {
      // A dashboard with no reader here (the calendar, the phone) draws and loads itself.
      let appNumbers: AppNumber[] | null = null;
      if (wanted.startsWith("app:")) {
        appNumbers = (
          await invoke<{ numbers: AppNumber[] }>("sidecar_call", {
            method: "app_board",
            params: { id: wanted.slice(4) },
          })
        ).numbers;
      }
      const found = appNumbers
        ? appTiles(appNumbers)
        : ((await READERS[wanted as DashboardId]?.()) ?? []);
      if (appNumbers) {
        // A connected app's percentages are drawn as rings; other numbers have no whole to measure against.
        const rings = appNumbers.flatMap((number) => {
          const percent = percentOf(number.value);
          return percent === null || number.error
            ? []
            : [{ label: number.label, percent, warn: percent >= 90 }];
        });
        panels = rings.length
          ? [{ kind: "rings", title: "Percentages", note: "From the connected app.", rings }]
          : [];
      }
      if (wanted !== current) return; // the user moved on while it was read
      tiles = found;
      readAt = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (cause) {
      if (wanted === current)
        error = cause instanceof Error ? cause.message : String(cause);
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
  // Columns for n tiles (about as many as rows), and how far the last tile stretches so no row ends empty.
  const columns = (n: number): number => Math.max(1, Math.ceil(Math.sqrt(n)));
  function spanLast(n: number): number {
    const left = n % columns(n);
    return left === 0 ? 1 : columns(n) - left + 1;
  }
  const title = $derived(
    items.find((item) => item.id === current)?.label ?? "",
  );
</script>

<!-- In the window's grid, not over it: the rail stays on the left and the agent cards on the right.
     Escape anywhere inside goes back to the graph. -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
  class="view"
  role="region"
  aria-label="Dashboards"
  tabindex="-1"
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
    <button
      type="button"
      onclick={() => {
        refreshed++;
        void load();
      }}>Refresh</button
    >
    <button
      type="button"
      class="close"
      aria-label="Close dashboards"
      onclick={onclose}>×</button
    >
  </header>
  <div class="body">
    <!-- Icons pick the dashboard. The graph is the main one: choosing it goes back to the normal layout. -->
    <nav class="icons" aria-label="Dashboards">
      <button
        type="button"
        class="icon-btn"
        aria-label="Graph"
        data-tip="Graph"
        onclick={onclose}
      >
        <DashIcon name="graph" />
      </button>
      {#each items as item (item.id)}
        <button
          type="button"
          class="icon-btn"
          class:on={current === item.id}
          aria-label={item.label}
          aria-pressed={current === item.id}
          data-tip={item.label}
          onclick={() => (current = item.id)}
        >
          <DashIcon name={item.id.startsWith("app:") ? "app" : item.id} />
        </button>
      {/each}
    </nav>
    <div
      class="board"
      role="tabpanel"
      aria-label={title}
      inert={prefs.dashboardsLocked}
      class:locked={prefs.dashboardsLocked}
    >
      <h3>{title}</h3>
      {#if current === "github"}
        <form class="repo" onsubmit={saveRepo}>
          <label for="dash-repo">Repository</label>
          <input
            id="dash-repo"
            type="text"
            placeholder="owner/name"
            bind:value={repoDraft}
          />
          <Button type="submit" disabled={!repoDraft.trim()}>Show</Button>
        </form>
        {#if prefs.dashboardsLocked && !prefs.dashboardRepo}
          <p class="note">
            Dashboards are locked, so the repository cannot be changed here.
            Unlock them in Settings, Dashboards.
          </p>
        {/if}
      {/if}
      {#if current === "calendar"}
        <div class="fill">
          {#key refreshed}<CalendarBoard />{/key}
        </div>
      {:else if current === "phone"}
        <div class="fill">
          {#key refreshed}<PhoneBoard />{/key}
        </div>
      {:else if error === NEEDS_REPO}
        <!-- The empty board says what to do in the middle of the space it will fill. -->
        <div class="empty" role="status">
          <p>
            Write a repository as owner/name and press Show. It is read with the
            gh tool you are logged in to.
          </p>
        </div>
      {:else if error}
        <ErrorRow message={error} onretry={() => void load()} />
      {:else if tiles === null}
        <Loading what={title} />
      {:else}
        <!-- About as many columns as rows, so a few tiles still fill the board in a grid, not one tall row. -->
        {#if panels.length}
          <div class="panels">
            {#each panels as panel (panel.title)}
              <AnalyticPanel {panel} />
            {/each}
          </div>
        {/if}
        <ul
          class="tiles"
          style:--cols={columns(tiles.length)}
        >
          {#each tiles as tile, i (tile.label)}
            <li
              class:warn={tile.tone === "warn"}
              style:grid-column={i === tiles.length - 1 && spanLast(tiles.length) > 1
                ? `span ${spanLast(tiles.length)}`
                : null}
            >
              <span class="label">{tile.label}</span>
              <div class="figure">
                <b>{tile.value}</b>
                {#if tile.share !== undefined}
                  <span
                    class="bar"
                    role="img"
                    aria-label={`${Math.round(tile.share * 100)}% of the whole`}
                  ><span style:width={`${tile.share * 100}%`}></span></span>
                {/if}
              </div>
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
    grid-area: board;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    height: 100%;
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
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    flex: 1;
    min-height: 0;
    padding-top: var(--space-3);
  }

  nav.icons {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  /* The icon's name shows under it on hover or keyboard focus, not beside it over the next icon. */
  .icon-btn:hover::after,
  .icon-btn:focus-visible::after {
    left: 50%;
    top: calc(100% + var(--space-1));
    transform: translateX(-50%);
  }

  .icon-btn {
    display: inline-grid;
    place-items: center;
    width: var(--size-40);
    height: var(--size-40);
    padding: 0;
    color: var(--color-text-muted);
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition:
      color var(--duration-fast) var(--ease-standard),
      background var(--duration-fast) var(--ease-standard);
  }

  .icon-btn:hover {
    color: var(--color-text);
    background: var(--color-bg-1);
  }

  .icon-btn.on {
    color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 14%, transparent);
    border-color: color-mix(in srgb, var(--color-accent) 45%, transparent);
  }

  .icon-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }



  /* The board fills its column: the tiles, the calendar and the phone stretch to the bottom. */
  .board {
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
  }

  .board > .tiles,
  .board > .empty,
  .fill {
    flex: 1 1 auto;
  }

  .empty {
    display: grid;
    place-items: center;
    margin-top: var(--space-3);
    padding: var(--space-6);
    color: var(--color-text-muted);
    text-align: center;
    border: 1px dashed var(--color-border);
    border-radius: var(--radius-md);
  }

  .empty p {
    max-width: 40ch;
    margin: 0;
  }

  .fill {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .repo {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    margin-top: var(--space-3);
  }

  .repo input {
    min-height: var(--size-28);
    padding: var(--space-1) var(--space-2);
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .repo input {
    width: min(320px, 100%);
  }

  /* Columns and rows of 1fr: however many tiles a dashboard has, they share the whole board. */
  .tiles {
    display: grid;
    grid-template-columns: repeat(var(--cols, 3), minmax(0, 1fr));
    grid-auto-rows: minmax(120px, 1fr);
    align-content: stretch;
    gap: var(--space-3);
    margin: var(--space-3) 0 0;
    padding: 0;
    list-style: none;
  }

  /* A tile: label at the top, the number in the middle sized to the tile, the note at the bottom.
     container-type lets the number scale with the tile (cqmin), so a big board reads from across the room. */
  .tiles li {
    position: relative;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: var(--space-2);
    min-width: 0;
    min-height: 0;
    padding: var(--space-4) var(--space-4) var(--space-3);
    overflow: hidden;
    container-type: size;
    background:
      linear-gradient(
        160deg,
        color-mix(in srgb, var(--color-accent) 7%, transparent),
        transparent 55%
      ),
      var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    transition:
      border-color var(--duration-fast) var(--ease-standard),
      translate var(--duration-fast) var(--ease-standard);
  }

  /* A thin accent bar along the top, the tile's one coloured mark. */
  .tiles li::before {
    content: "";
    position: absolute;
    inset: 0 0 auto;
    height: 3px;
    background: var(--color-accent);
    opacity: 0.6;
  }

  .tiles li:hover {
    border-color: color-mix(in srgb, var(--color-accent) 45%, var(--color-border));
    translate: 0 -1px;
  }

  /* A number that needs the user: the bar, the tint and the number turn to the warning colour. */
  .tiles li.warn {
    background:
      linear-gradient(
        160deg,
        color-mix(in srgb, var(--color-danger) 12%, transparent),
        transparent 60%
      ),
      var(--color-bg-1);
    border-color: color-mix(in srgb, var(--color-danger) 40%, var(--color-border));
  }

  .tiles li.warn::before {
    background: var(--color-danger);
    opacity: 1;
  }

  /* Charts and breakdowns sit above the tile grid, at the height their content needs. */
  .panels {
    display: grid;
    gap: var(--space-3);
    margin-top: var(--space-3);
    min-width: 0;
  }

  .panels > :global(.panel) {
    padding: var(--space-4);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .tiles li.warn b {
    color: var(--color-danger);
  }

  /* The share bar under a number: a track, and a fill in the tile's graph colour (the warn tile's, too). */
  .bar {
    display: block;
    height: 6px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-text-muted) 18%, transparent);
    overflow: hidden;
  }

  .bar > span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--color-graph-1);
    transition: width var(--duration-base) var(--ease-standard);
  }

  .tiles li.warn .bar > span {
    background: var(--color-danger);
  }

  .label {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    overflow-wrap: anywhere;
  }

  .note {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    overflow-wrap: anywhere;
  }

  /* The number and its share bar form one row of the tile, centred in the tile's middle row. */
  .figure {
    align-self: center;
    display: grid;
    gap: var(--space-2);
    width: 100%;
    min-width: 0;
  }

  .tiles b {
    font-size: clamp(var(--font-size-xl), 22cqmin, calc(var(--font-size-xl) * 5));
    font-variant-numeric: tabular-nums;
    line-height: 1;
    letter-spacing: -0.02em;
    overflow-wrap: anywhere;
  }

  @media (prefers-reduced-motion: reduce) {
    .tiles li {
      transition: none;
    }
    .tiles li:hover {
      translate: none;
    }
  }
</style>
