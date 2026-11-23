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
  import FinanceBoard from "./FinanceBoard.svelte";
  import AnalyticPanel from "./AnalyticPanel.svelte";
  import { prefs } from "../prefs.svelte.ts";
  import {
    activityByDay,
    short,
    activityTiles,
    breakdown,
    dayLabels,
    fraction,
    heatValues,
    percentOf,
    type Panel,
    appTiles,
    DASHBOARDS,
    systemTiles,
    type ActivityRow,
    type AppNumber,
    type DashboardId,
    type SystemShape,
    type Tile,
  } from "./model.ts";

  let { onclose, onsettings }: { onclose: () => void; onsettings: () => void } =
    $props();

  // A built-in dashboard's id, or "app:<id>" for a connected app.
  let current = $state<string>("apps");
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
        current = "apps";
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

  // Buttons above a board, set by the dashboard that reads them (the vault's "Ask the agent").
  let actions = $state<{ label: string; run: () => Promise<void> }[]>([]);
  let acting = $state(false);
  let actionNote = $state("");
  async function runAction(action: {
    run: () => Promise<void>;
  }): Promise<void> {
    acting = true;
    actionNote = "";
    try {
      await action.run();
    } catch (cause) {
      actionNote = cause instanceof Error ? cause.message : String(cause);
    } finally {
      acting = false;
    }
  }
  const NEEDS_APPS = "No app is connected yet.";

  type ProviderRow = {
    id: string;
    name: string;
    found: boolean;
    note: string;
    today: number;
    week: number;
    month: number;
    models: { model: string; tokens: number }[];
    days: number[];
  };
  type VaultShape = {
    stats: {
      notes: number;
      links: number;
      orphans: number;
      broken: number;
      important: number;
      projects: number;
      project_names: string[];
      daily: number;
      memory: number;
      tags: number;
      top_tags: [string, number][];
      folders: [string, number][];
      changed_week: number;
      recent: { path: string; title: string; at: string }[];
    };
    insights: {
      summary: string;
      numbers: { label: string; value: string; note: string }[];
      highlights: string[];
      generated_at: string;
    } | null;
  };
  type RepoRow = {
    repo: string;
    description?: string;
    private?: boolean;
    fork?: boolean;
    pushed?: string;
    language?: string;
    stars?: number;
    foreign?: boolean;
    agents: {
      name: string;
      commits: number;
      last: string;
      subjects: string[];
    }[];
  };
  const when = (iso: string): string =>
    iso
      ? new Date(iso).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";

  // What each dashboard reads. One that fails shows its reason and a Try again button.
  const READERS: Partial<Record<DashboardId, () => Promise<Tile[]>>> = {
    apps: async () => {
      if (!apps.length) throw new Error(NEEDS_APPS);
      const read = await Promise.all(
        apps.map(async (app) => {
          try {
            const found = await invoke<{ numbers: AppNumber[] }>(
              "sidecar_call",
              {
                method: "app_board",
                params: { id: app.id },
              },
            );
            return { app, numbers: found.numbers, error: "" };
          } catch (cause) {
            return { app, numbers: [] as AppNumber[], error: String(cause) };
          }
        }),
      );
      panels = read.map(({ app, numbers, error: failed }) => ({
        kind: "list",
        title: app.name,
        note: failed ? "Could not be read." : `${numbers.length} numbers`,
        rows: failed
          ? [{ title: failed, tone: "warn" as const }]
          : numbers.map((number) => ({
              title: number.label,
              meta: number.error ? "" : number.value,
              lines: number.error ? [number.error] : [],
              tone: number.error ? ("warn" as const) : ("plain" as const),
            })),
      }));
      return [
        {
          label: "Connected apps",
          value: String(apps.length),
          note: "Connect more in Settings, Dashboards.",
        },
        {
          label: "Numbers read",
          value: String(read.reduce((sum, r) => sum + r.numbers.length, 0)),
        },
        {
          label: "Could not be read",
          value: String(read.filter((r) => r.error).length),
          tone: read.some((r) => r.error) ? "warn" : "plain",
        },
      ];
    },
    providers: async () => {
      const found = await call<{ providers: ProviderRow[]; days: number }>(
        "provider_usage",
      );
      const seen = found.providers.filter((p) => p.found);
      const month = seen.reduce((sum, p) => sum + p.month, 0);
      const models = seen
        .flatMap((p) =>
          p.models.map(
            (m) => [`${p.name} · ${m.model}`, m.tokens] as [string, number],
          ),
        )
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8);
      const days = Array.from({ length: found.days }, (_, i) =>
        seen.reduce((sum, p) => sum + (p.days[i] ?? 0), 0),
      );
      panels = [
        {
          kind: "trend",
          title: "All providers, tokens per day",
          note: `Last ${found.days} days · ${short(month)} this month`,
          labels: dayLabels(found.days),
          values: days,
        },
        {
          kind: "breakdown",
          title: "Tokens this month by model",
          note: "The 8 models used most.",
          rows: breakdown(models, short),
        },
        {
          kind: "list",
          title: "How each is counted",
          note: "From each tool's own logs on this computer.",
          rows: found.providers.map((p) => ({
            title: p.name,
            badge: p.found ? "found" : "not on this computer",
            meta: p.found ? `${short(p.month)} this month` : "",
            lines: [
              ...(p.found
                ? [`Today ${short(p.today)} · last 7 days ${short(p.week)}`]
                : []),
              ...(p.note ? [p.note] : []),
            ],
            tone: p.found ? ("plain" as const) : ("warn" as const),
          })),
        },
      ];
      return seen.map((p) => ({
        label: p.name,
        value: p.found && !p.note.includes("no token") ? short(p.month) : "n/a",
        note: p.note.includes("no token")
          ? "Keeps no token counts here."
          : `This month. Today ${short(p.today)}, 7 days ${short(p.week)}.`,
        share: month ? fraction(p.month, month) : undefined,
      }));
    },
    vault: async () => {
      const found = await call<VaultShape>("vault_board");
      const s = found.stats;
      const insights = found.insights;
      actions = [
        {
          label: insights
            ? "Ask the agent to update the summary"
            : "Ask the agent for a summary",
          run: async () => {
            await call("vault_insights_request");
            actionNote =
              "Sent to Hippoherman. Its summary shows here once it writes it; press Refresh.";
          },
        },
      ];
      const extra = [
        ...(insights?.numbers ?? []).map(
          (n) => `${n.label}: ${n.value}${n.note ? ` (${n.note})` : ""}`,
        ),
        ...(insights?.highlights ?? []).map((h) => `Needs attention: ${h}`),
      ];
      panels = [
        {
          kind: "text",
          title: "The agent's summary",
          note: insights?.generated_at
            ? `Written ${when(insights.generated_at)}`
            : "Not written yet",
          text:
            (insights?.summary ||
              "No summary yet. Press Ask the agent for a summary: the main agent reads the vault and writes what matters, which projects are active and what is unfinished.") +
            (extra.length
              ? `\n\n${extra.map((line) => `• ${line}`).join("\n")}`
              : ""),
        },
        {
          kind: "list",
          title: "Projects",
          note: `${s.projects} found in project folders or tagged project.`,
          rows: s.project_names.map((name) => ({ title: name })),
          empty: "No project folder or project tag yet.",
        },
        {
          kind: "list",
          title: "Changed most recently",
          note: `${s.changed_week} notes changed in 7 days.`,
          rows: s.recent.slice(0, 8).map((r) => ({
            title: r.title,
            meta: when(r.at),
            lines: [r.path],
          })),
        },
        {
          kind: "breakdown",
          title: "Notes by folder",
          note: "The 8 biggest folders.",
          rows: breakdown(s.folders),
        },
      ];
      return [
        {
          label: "Notes",
          value: String(s.notes),
          note: `${s.links} links between them.`,
        },
        {
          label: "Projects",
          value: String(s.projects),
          note: "Folders and notes under Projects, or tagged project.",
        },
        { label: "Changed this week", value: String(s.changed_week) },
        {
          label: "Not linked",
          value: String(s.orphans),
          note: "Notes with no link in or out.",
          tone: s.notes && s.orphans / s.notes > 0.5 ? "warn" : "plain",
        },
        {
          label: "Broken links",
          value: String(s.broken),
          note: s.broken
            ? "Fix them with the link doctor in Settings."
            : "None.",
          tone: s.broken ? "warn" : "plain",
        },
      ];
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
      const found = await invoke<
        | { repos: RepoRow[]; others: RepoRow[]; days: number }
        | { error: string }
      >("sidecar_call", { method: "github_all" });
      if ("error" in found) throw new Error(found.error);
      const all = [...found.repos, ...found.others];
      const worked = all.filter((repo) => repo.agents.length);
      const commits = worked.reduce(
        (sum, repo) => sum + repo.agents.reduce((n, a) => n + a.commits, 0),
        0,
      );
      const row = (repo: RepoRow) => ({
        title: repo.repo,
        badge: repo.foreign
          ? "not yours"
          : [
              repo.private ? "private" : "public",
              repo.fork ? "fork" : "",
              repo.language,
            ]
              .filter(Boolean)
              .join(" · "),
        meta: repo.pushed ? `pushed ${when(repo.pushed)}` : "",
        lines: [
          ...(repo.description ? [repo.description] : []),
          ...repo.agents.map(
            (a) =>
              `${a.name}: ${a.commits} commit${a.commits === 1 ? "" : "s"} in ${found.days} days${a.last ? `, last ${a.last}` : ""}${a.subjects.length ? ` · ${a.subjects.slice(0, 3).join(" · ")}` : ""}`,
          ),
        ],
        tone: repo.agents.length ? ("good" as const) : ("plain" as const),
      });
      panels = [
        {
          kind: "list",
          title: "Where the agents worked",
          note: `Commits in the last ${found.days} days, from each agent's folder.`,
          rows: worked.map(row),
          empty: "No agent folder is a clone of a GitHub repository yet.",
          wide: true,
        },
        {
          kind: "list",
          title: "All repositories",
          note: `${found.repos.length}, newest push first.`,
          rows: found.repos.map(row),
          wide: true,
        },
      ];
      return [
        { label: "Repositories", value: String(found.repos.length) },
        {
          label: "Private",
          value: String(found.repos.filter((r) => r.private).length),
        },
        {
          label: "With agent work",
          value: String(worked.length),
          note: `In the last ${found.days} days.`,
        },
        {
          label: "Agent commits",
          value: String(commits),
          note: `In the last ${found.days} days.`,
        },
      ];
    },
    activity: async () => {
      const rows = (await call<{ rows: ActivityRow[] }>("activity")).rows;
      const days = activityByDay(rows);
      const count = (key: (row: ActivityRow) => string): [string, number][] => {
        const counts = new SvelteMap<string, number>();
        for (const row of rows) {
          const k = key(row);
          if (k) counts.set(k, (counts.get(k) ?? 0) + 1);
        }
        return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
      };
      const line = (row: ActivityRow) => ({
        title: row.text || row.method || row.tool || row.kind,
        badge: row.kind,
        meta: when(row.ts),
        lines: [
          [row.agent, row.tool || row.method].filter(Boolean).join(" · "),
        ].filter(Boolean),
        tone: row.kind === "error" ? ("warn" as const) : ("plain" as const),
      });
      panels = [
        {
          kind: "trend",
          title: "Events per day",
          note: "Last 14 days",
          labels: days.labels,
          values: days.values,
        },
        {
          kind: "breakdown",
          title: "By kind",
          note: `${rows.length} events read.`,
          rows: breakdown(
            count((row) => row.kind).map(
              ([k, n]) => [k, n, k === "error"] as [string, number, boolean],
            ),
          ),
        },
        {
          kind: "heat",
          title: "Activity, 13 weeks",
          note: "Each square is one day.",
          values: heatValues(rows),
        },
        {
          kind: "list",
          title: "Latest events",
          note: "Newest first.",
          rows: rows.slice(0, 20).map(line),
        },
      ];
      return activityTiles(rows);
    },
  };

  async function load(): Promise<void> {
    const wanted = current;
    tiles = null;
    panels = [];
    actions = [];
    actionNote = "";
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
          ? [
              {
                kind: "rings",
                title: "Percentages",
                note: "From the connected app.",
                rings,
              },
            ]
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
  // These keep their own layout; every other board fits the window: one row of numbers, panels below.
  const fit = $derived(!["calendar", "system", "phone"].includes(current));
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
      {#each items as item, i (item.id)}
        {#if item.id.startsWith("app:") && !items[i - 1]?.id.startsWith("app:")}
          <span class="divider" role="separator" aria-label="Connected apps"
          ></span>
        {/if}
        {#if item.id.startsWith("app:")}
          <!-- A connected app shows its name, not an icon. -->
          <button
            type="button"
            class="icon-btn app-btn"
            class:on={current === item.id}
            aria-pressed={current === item.id}
            onclick={() => (current = item.id)}
          >
            {item.label}
          </button>
        {:else}
          <button
            type="button"
            class="icon-btn"
            class:on={current === item.id}
            aria-label={item.label}
            aria-pressed={current === item.id}
            data-tip={item.label}
            onclick={() => (current = item.id)}
          >
            <DashIcon name={item.id} />
          </button>
        {/if}
      {/each}
    </nav>
    <div
      class="board"
      role="tabpanel"
      aria-label={title}
      inert={prefs.dashboardsLocked}
      class:locked={prefs.dashboardsLocked}
      class:grow={current === "calendar"}
      class:fit
    >
      <h3>{title}</h3>
      {#if actions.length}
        <div class="actions">
          {#each actions as action (action.label)}
            <Button
              variant="primary"
              disabled={acting}
              onclick={() => runAction(action)}>{action.label}</Button
            >
          {/each}
          {#if actionNote}<span class="note" role="status">{actionNote}</span
            >{/if}
        </div>
      {/if}
      {#if current === "calendar"}
        <div class="fill">
          {#key refreshed}<CalendarBoard />{/key}
        </div>
      {:else if current === "phone"}
        <div class="fill">
          {#key refreshed}<PhoneBoard />{/key}
        </div>
      {:else if current === "finance"}
        <div class="fill">
          {#key refreshed}<FinanceBoard />{/key}
        </div>
      {:else if error === NEEDS_APPS}
        <!-- The empty board says what to do in the middle of the space it will fill. -->
        <div class="empty" role="status">
          <p>
            No app is connected yet. Connect one in Settings, Dashboards, and
            its numbers show here, every app on one board.
          </p>
          <Button variant="primary" onclick={onsettings}>Open Settings</Button>
        </div>
      {:else if error}
        <ErrorRow message={error} onretry={() => void load()} />
      {:else if tiles === null}
        <Loading what={title} />
      {:else}
        <ul
          class="tiles"
          style:--cols={fit ? Math.min(tiles.length, 6) : columns(tiles.length)}
        >
          {#each tiles as tile, i (tile.label)}
            <li
              class:warn={tile.tone === "warn"}
              style:grid-column={!fit &&
              i === tiles.length - 1 &&
              spanLast(tiles.length) > 1
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
                    ><span style:width={`${tile.share * 100}%`}></span></span
                  >
                {/if}
              </div>
              {#if tile.note}<span class="note">{tile.note}</span>{/if}
            </li>
          {/each}
        </ul>
        <!-- About as many columns as rows, so a few tiles still fill the board in a grid, not one tall row. -->
        {#if panels.length}
          <div
            class="panels"
            class:odd={panels.length > 1 && panels.length % 2 === 1}
            style:--pc={panels.length > 1 ? 2 : 1}
          >
            {#each panels as panel (panel.title)}
              <AnalyticPanel {panel} fill={fit} />
            {/each}
          </div>
        {/if}
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
    align-items: center;
  }

  /* A thin upright line between the built-in dashboards and the connected apps. */
  nav.icons .divider {
    align-self: stretch;
    width: 1px;
    margin: var(--space-1) var(--space-2);
    background: var(--color-border);
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

  /* A connected app: its name as text, as tall as the icons. */
  .icon-btn.app-btn {
    width: auto;
    padding: 0 var(--space-3);
    font-size: var(--font-size-sm);
    white-space: nowrap;
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

  /* The calendar's hours fill the height of the window and scroll inside it. */
  .board.grow {
    flex: 1 1 auto;
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
    background: var(--pop-bg);
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
      radial-gradient(
        120% 100% at 50% 100%,
        color-mix(in srgb, var(--color-accent) 16%, transparent),
        transparent 70%
      ),
      var(--tile-grid), var(--color-bg-1);
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
    border-color: color-mix(
      in srgb,
      var(--color-accent) 45%,
      var(--color-border)
    );
    translate: 0 -1px;
  }

  /* A number that needs the user: the bar, the tint and the number turn to the warning colour. */
  .tiles li.warn {
    background:
      radial-gradient(
        120% 100% at 50% 100%,
        color-mix(in srgb, var(--color-danger) 18%, transparent),
        transparent 70%
      ),
      var(--tile-grid), var(--color-bg-1);
    border-color: color-mix(
      in srgb,
      var(--color-danger) 40%,
      var(--color-border)
    );
  }

  .tiles li.warn::before {
    background: var(--color-danger);
    opacity: 1;
  }

  /* Charts and breakdowns sit above the tile grid, at the height their content needs. */
  .panels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
    gap: var(--space-3);
    margin-top: var(--space-3);
    min-width: 0;
  }

  .panels > :global(.panel.wide) {
    grid-column: 1 / -1;
  }

  /* A board that fits the window: the page never scrolls. The numbers are one short row, the panels
     share the rest in two columns, and a long list scrolls inside its own panel. */
  .board.fit {
    flex: 1 1 auto;
    overflow: hidden;
  }

  .board.fit > .tiles {
    flex: 0 0 auto;
    grid-auto-rows: clamp(84px, 11vh, 120px);
  }

  .board.fit .tiles li {
    padding: var(--space-3) var(--space-4);
  }

  .board.fit .tiles b {
    font-size: clamp(
      var(--font-size-lg),
      34cqmin,
      calc(var(--font-size-xl) * 2)
    );
  }

  .board.fit .tiles .note {
    font-size: var(--font-size-xs);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .board.fit > .panels {
    flex: 1 1 0;
    min-height: 0;
    grid-template-columns: repeat(var(--pc, 2), minmax(0, 1fr));
    grid-auto-rows: minmax(0, 1fr);
  }

  .board.fit > .panels > :global(.panel.wide) {
    grid-column: auto;
  }

  /* Three panels: the first runs across the top, the other two share the row below. */
  .board.fit > .panels.odd > :global(.panel:first-child) {
    grid-column: 1 / -1;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    margin-top: var(--space-2);
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
    font-size: clamp(
      var(--font-size-xl),
      22cqmin,
      calc(var(--font-size-xl) * 5)
    );
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
