// Pure helpers for the dashboards: they turn the backend's answers into tiles. No DOM or Tauri, so they
// run under node --test.

export type Tile = {
  label: string;
  value: string;
  /** A short line under the number: what it counts, or what to do about it. */
  note?: string;
  /** "warn" marks a number that needs the user. */
  tone?: "plain" | "warn";
};

/** The dashboards built into the app, in the order the list shows them. */
export const DASHBOARDS = [
  { id: "overview", label: "Overview" },
  { id: "agents", label: "Agents and spend" },
  { id: "tasks", label: "Tasks" },
  { id: "notes", label: "Notes" },
  { id: "system", label: "System" },
  { id: "activity", label: "Activity" },
] as const;
export type DashboardId = (typeof DASHBOARDS)[number]["id"];

export type TaskRow = { status: string; waiting?: boolean };
export type GraphShape = {
  nodes: { id: string; tags: string[] }[];
  edges: [string, string][];
};
export type SystemShape = {
  cpu: number;
  ram: number;
  swap: number;
  disk: number;
  disk_free: number;
};
export type ActivityRow = { ts: string; kind: string };

export function short(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

const COLUMNS = ["todo", "doing", "blocked", "done"] as const;

export function taskTiles(tasks: TaskRow[]): Tile[] {
  const waiting = tasks.filter((task) => task.waiting).length;
  return [
    ...COLUMNS.map((column) => ({
      label: column.charAt(0).toUpperCase() + column.slice(1),
      value: String(tasks.filter((task) => task.status === column).length),
    })),
    {
      label: "Waiting on you",
      value: String(waiting),
      note: waiting ? "Answer them on the ask me tab." : "Nothing needs you.",
      tone: waiting ? ("warn" as const) : ("plain" as const),
    },
  ];
}

export function noteTiles(graph: GraphShape): Tile[] {
  const linked = new Set(graph.edges.flat());
  const orphans = graph.nodes.filter((node) => !linked.has(node.id)).length;
  const tags = new Map<string, number>();
  for (const node of graph.nodes)
    for (const tag of node.tags) tags.set(tag, (tags.get(tag) ?? 0) + 1);
  const top = [...tags.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
  )[0];
  return [
    { label: "Notes", value: String(graph.nodes.length) },
    { label: "Links", value: String(graph.edges.length) },
    {
      label: "Notes with no links",
      value: String(orphans),
      tone: orphans ? "warn" : "plain",
    },
    { label: "Tags", value: String(tags.size) },
    {
      label: "Most used tag",
      value: top ? `#${top[0]}` : "None",
      note: top ? `On ${top[1]} notes.` : "No note has a tag yet.",
    },
  ];
}

export function systemTiles(system: SystemShape): Tile[] {
  const percent = (label: string, value: number, limit: number): Tile => ({
    label,
    value: `${Math.round(value)}%`,
    tone: value >= limit ? "warn" : "plain",
  });
  return [
    percent("CPU", system.cpu, 90),
    percent("RAM", system.ram, 90),
    percent("Swap", system.swap, 50),
    percent("Disk", system.disk, 90),
    { label: "Free disk", value: `${system.disk_free} GB` },
  ];
}

export function spendTiles(byAgent: Record<string, number>): Tile[] {
  const rows = Object.entries(byAgent).sort((a, b) => b[1] - a[1]);
  const total = rows.reduce((sum, [, used]) => sum + used, 0);
  return [
    { label: "Tokens today", value: short(total), note: "All agents." },
    ...rows.map(([agent, used]) => ({
      label: agent,
      value: short(used),
      note: total ? `${Math.round((100 * used) / total)}% of today.` : "",
    })),
  ];
}

export function activityTiles(rows: ActivityRow[]): Tile[] {
  const kinds = new Map<string, number>();
  for (const row of rows) kinds.set(row.kind, (kinds.get(row.kind) ?? 0) + 1);
  const newest = rows
    .map((row) => row.ts)
    .sort()
    .at(-1);
  return [
    { label: "Events kept", value: String(rows.length) },
    ...[...kinds.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([kind, count]) => ({ label: kind, value: String(count) })),
    {
      label: "Newest",
      value: newest ? newest.slice(0, 16).replace("T", " ") : "None",
    },
  ];
}

export function overviewTiles(found: {
  agents: number;
  tokens: number;
  tasks: TaskRow[];
  asks: number;
  system: SystemShape | null;
}): Tile[] {
  const open = found.tasks.filter((task) => task.status !== "done").length;
  return [
    {
      label: "Agents",
      value: String(found.agents),
      note: "Added to this office.",
    },
    { label: "Tokens today", value: short(found.tokens) },
    { label: "Open tasks", value: String(open) },
    {
      label: "Questions waiting",
      value: String(found.asks),
      tone: found.asks ? "warn" : "plain",
    },
    {
      label: "CPU and RAM",
      value: found.system
        ? `${Math.round(found.system.cpu)}% · ${Math.round(found.system.ram)}%`
        : "Not read",
    },
  ];
}
