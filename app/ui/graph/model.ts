// Pure graph logic: layout, camera, hit testing, filtering. No DOM or WebGL, so it runs under node --test.

export interface GraphNode {
  id: string;
  title: string;
  tags: string[];
  /** True for notes the assistant created (frontmatter created_by: assistant). */
  memory?: boolean;
}

export interface GraphData {
  nodes: GraphNode[];
  /** Pairs of node ids, as the core index returns them. */
  edges: [string, string][];
}

export interface LayoutPreset {
  iterations: number;
  /** Random repulsion partners sampled per node per iteration. */
  samples: number;
  /** Device pixel ratio cap for the canvas. */
  dprCap: number;
}

// Low-power preset: fewer layout steps and a 1x canvas, for the Intel HD 5500 dev machine.
// shortcut: repulsion is sampled, not exact, so dense clusters spread less; raise samples for quality.
export const LOW_POWER: LayoutPreset = {
  iterations: 150,
  samples: 12,
  dprCap: 1,
};

export interface Camera {
  /** Screen pixels of pan from the canvas origin. */
  x: number;
  y: number;
  zoom: number;
}

export const MIN_ZOOM = 0.05;
export const MAX_ZOOM = 8;

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Interleaved x, y world positions for each node index. Deterministic for a given seed. */
export function layout(
  nodeCount: number,
  edges: ReadonlyArray<readonly [number, number]>,
  preset: LayoutPreset = LOW_POWER,
  seed = 1,
): Float32Array<ArrayBuffer> {
  const rand = mulberry32(seed);
  const pos = new Float32Array(nodeCount * 2);
  const spread = Math.sqrt(nodeCount) * 12;
  for (let i = 0; i < nodeCount; i++) {
    const r = Math.sqrt(rand()) * spread;
    const a = rand() * Math.PI * 2;
    pos[2 * i] = Math.cos(a) * r;
    pos[2 * i + 1] = Math.sin(a) * r;
  }
  const k = spread / Math.sqrt(nodeCount) + 1; // ideal spacing
  const disp = new Float32Array(nodeCount * 2);
  for (let it = 0; it < preset.iterations; it++) {
    const temp = spread * 0.1 * (1 - it / preset.iterations) + 0.5;
    disp.fill(0);
    for (let i = 0; i < nodeCount; i++) {
      for (let s = 0; s < preset.samples; s++) {
        const j = Math.floor(rand() * nodeCount);
        if (j === i) continue;
        const dx = (pos[2 * i] ?? 0) - (pos[2 * j] ?? 0);
        const dy = (pos[2 * i + 1] ?? 0) - (pos[2 * j + 1] ?? 0);
        const d2 = dx * dx + dy * dy + 0.01;
        const f = (k * k) / d2; // repulsion ~ 1/d, scaled to the sample count
        add(disp, 2 * i, dx * f * (nodeCount / preset.samples));
        add(disp, 2 * i + 1, dy * f * (nodeCount / preset.samples));
      }
    }
    for (const [a, b] of edges) {
      const dx = (pos[2 * a] ?? 0) - (pos[2 * b] ?? 0);
      const dy = (pos[2 * a + 1] ?? 0) - (pos[2 * b + 1] ?? 0);
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const f = (d * d) / k / d; // attraction ~ d
      add(disp, 2 * a, -dx * f);
      add(disp, 2 * a + 1, -dy * f);
      add(disp, 2 * b, dx * f);
      add(disp, 2 * b + 1, dy * f);
    }
    for (let i = 0; i < nodeCount; i++) {
      const dx = disp[2 * i] ?? 0;
      const dy = disp[2 * i + 1] ?? 0;
      const m = Math.sqrt(dx * dx + dy * dy) + 1e-9;
      const step = Math.min(m, temp) / m;
      pos[2 * i] = (pos[2 * i] ?? 0) + dx * step - (pos[2 * i] ?? 0) * 0.002; // weak pull to the centre
      pos[2 * i + 1] =
        (pos[2 * i + 1] ?? 0) + dy * step - (pos[2 * i + 1] ?? 0) * 0.002;
    }
  }
  return pos;
}

function add(arr: Float32Array, i: number, v: number): void {
  arr[i] = (arr[i] ?? 0) + v;
}

export function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/** Zoom by `factor` keeping the world point under screen point (sx, sy) fixed. */
export function zoomAt(
  cam: Camera,
  sx: number,
  sy: number,
  factor: number,
): Camera {
  const zoom = clampZoom(cam.zoom * factor);
  const ratio = zoom / cam.zoom;
  return {
    zoom,
    x: sx - (sx - cam.x) * ratio,
    y: sy - (sy - cam.y) * ratio,
  };
}

/** Camera that puts world point (wx, wy) at the centre of a width x height canvas. */
export function centerOn(
  wx: number,
  wy: number,
  zoom: number,
  width: number,
  height: number,
): Camera {
  return { zoom, x: width / 2 - wx * zoom, y: height / 2 - wy * zoom };
}

export function screenToWorld(
  cam: Camera,
  sx: number,
  sy: number,
): [number, number] {
  return [(sx - cam.x) / cam.zoom, (sy - cam.y) / cam.zoom];
}

/** Index of the node under screen point (sx, sy) within `radius` pixels, or -1. Nearest wins. */
export function hitTest(
  pos: ArrayLike<number>,
  cam: Camera,
  sx: number,
  sy: number,
  radius: number,
): number {
  let best = -1;
  let bestD = radius * radius;
  for (let i = 0; i * 2 < pos.length; i++) {
    const dx = (pos[2 * i] ?? 0) * cam.zoom + cam.x - sx;
    const dy = (pos[2 * i + 1] ?? 0) * cam.zoom + cam.y - sy;
    const d = dx * dx + dy * dy;
    if (d <= bestD) {
      bestD = d;
      best = i;
    }
  }
  return best;
}

export interface Filter {
  query: string;
  tag: string | null;
  /** Only assistant memory notes pass. */
  memory?: boolean;
}

/** Per node: true if it passes the search text and tag filter. An empty filter passes everything. */
export function matchFilter(
  nodes: readonly GraphNode[],
  filter: Filter,
): boolean[] {
  const q = filter.query.trim().toLocaleLowerCase();
  return nodes.map((n) => {
    if (filter.tag && !n.tags.includes(filter.tag)) return false;
    if (filter.memory && !n.memory) return false;
    if (!q) return true;
    return (
      n.title.toLocaleLowerCase().includes(q) ||
      n.id.toLocaleLowerCase().includes(q)
    );
  });
}

/** Every tag used by at least one node, sorted. */
export function allTags(nodes: readonly GraphNode[]): string[] {
  const set = new Set<string>();
  for (const n of nodes) for (const t of n.tags) set.add(t);
  return [...set].sort((a, b) => a.localeCompare(b));
}

/** Per node: how many links touch it. Self-links and links to unknown ids are not counted. */
export function linkCounts(
  nodes: readonly GraphNode[],
  edges: ReadonlyArray<readonly [string, string]>,
): number[] {
  const index = new Map(nodes.map((n, i) => [n.id, i]));
  const counts = nodes.map(() => 0);
  for (const [a, b] of edges) {
    const ia = index.get(a);
    const ib = index.get(b);
    if (ia === undefined || ib === undefined || ia === ib) continue;
    counts[ia] = (counts[ia] ?? 0) + 1;
    counts[ib] = (counts[ib] ?? 0) + 1;
  }
  return counts;
}

/** Each tag used by at least one node, with how many nodes carry it. Sorted by tag. */
export function tagCounts(nodes: readonly GraphNode[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const n of nodes)
    for (const t of n.tags) counts.set(t, (counts.get(t) ?? 0) + 1);
  return [...counts].sort(([a], [b]) => a.localeCompare(b));
}

/** Node radius in px: 4 for a note with no links, growing with its link count up to 10. */
export function nodeRadius(links: number, selected: boolean): number {
  const size = 4 + Math.min(6, Math.sqrt(links) * 1.5);
  return selected ? Math.max(7, size) : size;
}

export type GraphLayout = "arc" | "force";

/** Arc layout: world px between two rows of the note column. */
export const ARC_ROW = 10;
/** Arc layout: straight pieces each link curve is drawn with. */
export const ARC_SEGMENTS = 16;

/** Arc layout: the note column sits on x = 0, node i on row rows[i]. */
export function arcLayout(rows: ArrayLike<number>): Float32Array<ArrayBuffer> {
  const pos = new Float32Array(rows.length * 2);
  for (let i = 0; i < rows.length; i++)
    pos[2 * i + 1] = (rows[i] ?? 0) * ARC_ROW;
  return pos;
}

/** Leftmost x any arc or group centre can reach for `count` rows, so the fit can frame them all. */
export function arcReach(count: number): number {
  return Math.min(bowReach(count), arcCentreX(count));
}

function bowReach(count: number): number {
  return -0.375 * Math.max(0, count - 1) * ARC_ROW;
}

/** Arc layout: x of the group centres, left of the note column and the arcs, so each unlinked note has a string to its centre. */
export function arcCentreX(count: number): number {
  return Math.min(-4 * ARC_ROW, bowReach(count) / 2);
}

/**
 * Arc layout hubs: the note column, then one centre per group (at the middle row of its run), then the core.
 * Node index: note i is i, centre g is count + g, the core is count + groups.
 * `edges` joins every note to its group's centre, and each centre to the core.
 */
export function arcHubs(
  rows: ArrayLike<number>,
  of: ArrayLike<number>,
  groups: number,
): { pos: Float32Array<ArrayBuffer>; edges: Uint32Array<ArrayBuffer> } {
  const count = rows.length;
  if (!count) return { pos: new Float32Array(0), edges: new Uint32Array(0) };
  const pos = new Float32Array((count + groups + 1) * 2);
  pos.set(arcLayout(rows));
  const lo = Array.from({ length: groups }, () => Infinity);
  const hi = Array.from({ length: groups }, () => -Infinity);
  for (let i = 0; i < count; i++) {
    const g = of[i] ?? 0;
    lo[g] = Math.min(lo[g] ?? Infinity, rows[i] ?? 0);
    hi[g] = Math.max(hi[g] ?? -Infinity, rows[i] ?? 0);
  }
  const cx = arcCentreX(count);
  const edges: number[] = [];
  for (let g = 0; g < groups; g++) {
    const at = 2 * (count + g);
    pos[at] = cx;
    pos[at + 1] = (((lo[g] ?? 0) + (hi[g] ?? 0)) / 2) * ARC_ROW;
    edges.push(count + g, count + groups);
  }
  for (let i = 0; i < count; i++) edges.push(i, count + (of[i] ?? 0));
  // The core sits on the column's middle row, so the arcs curve around it.
  const core = 2 * (count + groups);
  pos[core] = 0;
  pos[core + 1] = ((count - 1) / 2) * ARC_ROW;
  return { pos, edges: Uint32Array.from(edges) };
}

/** Row per node: sorted by group, then title, so each group is one run of rows. */
export function arcRows(nodes: readonly GraphNode[]): number[] {
  const order = nodes
    .map((_, i) => i)
    .sort((a, b) => {
      const na = nodes[a];
      const nb = nodes[b];
      if (!na || !nb) return 0;
      return (
        groupOf(na).localeCompare(groupOf(nb)) ||
        na.title.localeCompare(nb.title)
      );
    });
  const rows = nodes.map(() => 0);
  order.forEach((node, row) => (rows[node] = row));
  return rows;
}

/** The group a note is coloured by: its first tag, else its top folder, else "Root" (a note at the vault root). Every note has a group. */
export function groupOf(n: GraphNode): string {
  // Trimmed, so a blank tag or folder name falls through to the next rule instead of an unnamed group.
  const tag = n.tags[0]?.trim();
  if (tag) return tag;
  const slash = n.id.indexOf("/");
  return (slash > 0 && n.id.slice(0, slash).trim()) || "Root";
}

/** Group names sorted, and per node the index of its group in that list. */
export function groupsOf(nodes: readonly GraphNode[]): {
  names: string[];
  of: number[];
} {
  const names = [...new Set(nodes.map(groupOf))].sort((a, b) =>
    a.localeCompare(b),
  );
  const index = new Map(names.map((g, i) => [g, i]));
  return { names, of: nodes.map((n) => index.get(groupOf(n)) ?? 0) };
}

/**
 * Writes one link as ARC_SEGMENTS segments into `out` from offset `at`, and returns the next offset.
 * The curve is a cubic that bows left of both ends, so a link between far rows bows further.
 */
export function arcSegments(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  out: Float32Array,
  at: number,
): number {
  const cx = Math.min(ax, bx) - 0.5 * Math.abs(ay - by);
  let px = ax;
  let py = ay;
  for (let s = 1; s <= ARC_SEGMENTS; s++) {
    const t = s / ARC_SEGMENTS;
    const u = 1 - t;
    const x =
      u * u * u * ax + 3 * u * u * t * cx + 3 * u * t * t * cx + t * t * t * bx;
    const y =
      u * u * u * ay + 3 * u * u * t * ay + 3 * u * t * t * by + t * t * t * by;
    out[at++] = px;
    out[at++] = py;
    out[at++] = x;
    out[at++] = y;
    px = x;
    py = y;
  }
  return at;
}

/** World-space segments (four floats each) for every link drawn as an arc. `edges` is node index pairs. */
export function arcLines(
  pos: ArrayLike<number>,
  edges: Uint32Array,
): Float32Array<ArrayBuffer> {
  const out = new Float32Array((edges.length / 2) * ARC_SEGMENTS * 4);
  let at = 0;
  for (let e = 0; e < edges.length; e += 2) {
    const a = (edges[e] ?? 0) * 2;
    const b = (edges[e + 1] ?? 0) * 2;
    at = arcSegments(
      pos[a] ?? 0,
      pos[a + 1] ?? 0,
      pos[b] ?? 0,
      pos[b + 1] ?? 0,
      out,
      at,
    );
  }
  return out;
}

/** World-space straight segments for every link: the force layout's edges. */
export function straightLines(
  pos: ArrayLike<number>,
  edges: Uint32Array,
): Float32Array<ArrayBuffer> {
  const out = new Float32Array(edges.length * 2);
  for (let e = 0; e < edges.length; e += 2) {
    const a = (edges[e] ?? 0) * 2;
    const b = (edges[e + 1] ?? 0) * 2;
    const at = e * 2;
    out[at] = pos[a] ?? 0;
    out[at + 1] = pos[a + 1] ?? 0;
    out[at + 2] = pos[b] ?? 0;
    out[at + 3] = pos[b + 1] ?? 0;
  }
  return out;
}
