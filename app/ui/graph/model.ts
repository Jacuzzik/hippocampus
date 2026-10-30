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

/** Simulation steps run before the first frame, and the canvas pixel ratio cap. */
export interface LayoutPreset {
  iterations: number;
  dprCap: number;
}

// Low-power preset: a 1x canvas, and the layout settles in this many steps before the first frame.
export const LOW_POWER: LayoutPreset = {
  iterations: 300,
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

// Force simulation, as in Obsidian's graph view: a centre force pulls notes to the core, repel pushes every pair apart, and a link force holds linked notes about LINK_DISTANCE apart.
export const LINK_DISTANCE = 15;
export const CENTER_STRENGTH = 0.03;
/** Centre pull multiplier for notes with no links, so the lonely ones stay nearer the middle. shortcut: 1.5 is tuned on the 1,175-note proxy; at 2 or more the lonely notes stack on one another, so re-check on the real vault before raising it. */
export const LONELY_PULL = 1.5;
/** Repel charge: force = strength / distance, as d3's many-body force. With 1/d² it packed 1,167 notes into dots 8 px apart. */
export const REPEL_STRENGTH = 300;
/** Repel reaches this far, in world px. shortcut: a cutoff, not an all-pairs charge, so far-apart clusters push each other less; upgrade to Barnes-Hut if they drift together. */
export const REPEL_RANGE = 200;
/** Repel softening, px²: notes closer than ~32 px push with a finite force. Without it, the first steps overshoot and settle into a regular lattice. shortcut: tuned on a 1,175-note proxy; 2,500 collapses notes onto one point, so re-check on the real vault before raising it. */
export const REPEL_SOFTEN = 1000;
/** Share of velocity kept each step (d3's default friction). */
const VELOCITY_KEEP = 0.6;
/** Heat falls from 1 to ALPHA_MIN over 300 steps. A grab or a drop re-heats it to REHEAT, so the neighbours settle back. */
const ALPHA_MIN = 0.001;
const ALPHA_DECAY = 1 - ALPHA_MIN ** (1 / 300);
export const REHEAT = 0.3;

export interface Sim {
  /** Interleaved x, y per node. The core is the last node, pinned at (0, 0). */
  pos: Float32Array<ArrayBuffer>;
  vel: Float32Array<ArrayBuffer>;
  /** Interleaved note index pairs for the links. */
  edges: Uint32Array;
  /** Links per note, for the link force. */
  deg: Uint32Array;
  /** Notes, the core excluded. */
  count: number;
  /** The note held under the pointer, pinned in place, or -1. */
  grabbed: number;
  /** Heat: how far the simulation still moves. */
  alpha: number;
}

/** A simulation of `count` notes linked by `pairs`, started on a seeded random disc with the core at the origin. */
export function newSim(
  count: number,
  pairs: ReadonlyArray<readonly [number, number]>,
  seed = 1,
): Sim {
  const rand = mulberry32(seed);
  const pos = new Float32Array((count + 1) * 2);
  const spread = Math.sqrt(count) * LINK_DISTANCE;
  for (let i = 0; i < count; i++) {
    const r = Math.sqrt(rand()) * spread;
    const a = rand() * Math.PI * 2;
    pos[2 * i] = Math.cos(a) * r;
    pos[2 * i + 1] = Math.sin(a) * r;
  }
  const edges = new Uint32Array(pairs.length * 2);
  const deg = new Uint32Array(count);
  pairs.forEach(([a, b], e) => {
    edges[2 * e] = a;
    edges[2 * e + 1] = b;
    deg[a] = (deg[a] ?? 0) + 1;
    deg[b] = (deg[b] ?? 0) + 1;
  });
  return {
    pos,
    vel: new Float32Array(pos.length),
    edges,
    deg,
    count,
    grabbed: -1,
    alpha: 1,
  };
}

/** One simulation step. Returns false, and does nothing, once the heat has settled. */
export function tick(sim: Sim): boolean {
  if (sim.alpha < ALPHA_MIN) return false;
  const { pos, vel, edges, deg, count, grabbed } = sim;
  const a = sim.alpha;
  const cx = pos[2 * count] ?? 0;
  const cy = pos[2 * count + 1] ?? 0;

  // Repel: notes in the same or a neighbouring grid cell push each other apart, with a 1/d² charge.
  const cell = (v: number) => Math.floor(v / REPEL_RANGE);
  const key = (gx: number, gy: number) => (gx + 1e4) * 2e4 + (gy + 1e4);
  const cells = new Map<number, number[]>();
  for (let i = 0; i < count; i++) {
    const k = key(cell(pos[2 * i] ?? 0), cell(pos[2 * i + 1] ?? 0));
    const list = cells.get(k);
    if (list) list.push(i);
    else cells.set(k, [i]);
  }
  const reach2 = REPEL_RANGE * REPEL_RANGE;
  for (let i = 0; i < count; i++) {
    const x = pos[2 * i] ?? 0;
    const y = pos[2 * i + 1] ?? 0;
    const gx = cell(x);
    const gy = cell(y);
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++)
        for (const j of cells.get(key(gx + dx, gy + dy)) ?? []) {
          if (j === i) continue;
          const ddx = x - (pos[2 * j] ?? 0);
          const ddy = y - (pos[2 * j + 1] ?? 0);
          const d2 = ddx * ddx + ddy * ddy + REPEL_SOFTEN;
          if (d2 > reach2) continue;
          const f = (REPEL_STRENGTH * a) / d2;
          add(vel, 2 * i, ddx * f);
          add(vel, 2 * i + 1, ddy * f);
        }
  }

  // Link: each link pulls or pushes its ends toward LINK_DISTANCE. Each end takes 1/its own degree, so a hub's links cannot overshoot and diverge.
  for (let e = 0; e < edges.length; e += 2) {
    const i = edges[e] ?? 0;
    const j = edges[e + 1] ?? 0;
    const dx = (pos[2 * j] ?? 0) - (pos[2 * i] ?? 0);
    const dy = (pos[2 * j + 1] ?? 0) - (pos[2 * i + 1] ?? 0);
    const d = Math.sqrt(dx * dx + dy * dy) || 1e-6;
    const k =
      ((d - LINK_DISTANCE) / d) * a;
    add(vel, 2 * i, (dx * k) / (deg[i] ?? 1));
    add(vel, 2 * i + 1, (dy * k) / (deg[i] ?? 1));
    add(vel, 2 * j, (-dx * k) / (deg[j] ?? 1));
    add(vel, 2 * j + 1, (-dy * k) / (deg[j] ?? 1));
  }

  // Centre, then move. The grabbed note stays under the pointer.
  for (let i = 0; i < count; i++) {
    const x = pos[2 * i] ?? 0;
    const y = pos[2 * i + 1] ?? 0;
    const grab = i === grabbed;
    const pull = CENTER_STRENGTH * a * ((deg[i] ?? 0) === 0 ? LONELY_PULL : 1);
    const vx = grab ? 0 : ((vel[2 * i] ?? 0) + (cx - x) * pull) * VELOCITY_KEEP;
    const vy = grab ? 0 : ((vel[2 * i + 1] ?? 0) + (cy - y) * pull) * VELOCITY_KEEP;
    vel[2 * i] = vx;
    vel[2 * i + 1] = vy;
    if (!grab) {
      pos[2 * i] = x + vx;
      pos[2 * i + 1] = y + vy;
    }
  }
  sim.alpha -= sim.alpha * ALPHA_DECAY;
  return true;
}

/** Runs up to `steps` ticks at once, so a fresh layout is already settled before the first frame. */
export function settle(sim: Sim, steps: number): void {
  for (let s = 0; s < steps; s++) if (!tick(sim)) break;
}

/** Heats the simulation so it moves again, e.g. after a note is grabbed or dropped. */
export function reheat(sim: Sim): void {
  sim.alpha = Math.max(sim.alpha, REHEAT);
}

/** Settled x, y per note for a fresh layout. Deterministic for a seed. */
export function layout(
  count: number,
  pairs: ReadonlyArray<readonly [number, number]>,
  preset: LayoutPreset = LOW_POWER,
  seed = 1,
): Float32Array<ArrayBuffer> {
  const sim = newSim(count, pairs, seed);
  settle(sim, preset.iterations);
  return sim.pos.slice(0, count * 2);
}

/** Label opacity at a zoom: hidden below LABEL_FADE_START, fully shown from LABEL_FADE_FULL. Obsidian's text fade threshold. */
export const LABEL_FADE_START = 0.5;
export const LABEL_FADE_FULL = 1;
export function labelAlpha(zoom: number): number {
  const t = (zoom - LABEL_FADE_START) / (LABEL_FADE_FULL - LABEL_FADE_START);
  return Math.min(1, Math.max(0, t));
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

/** Node shapes, as the per-instance value the renderers read: a filled disk (the core), a hollow square, a hollow tall rectangle. */
export const SHAPE_DISK = 0;
export const SHAPE_SQUARE = 1;
export const SHAPE_TALL = 2;
/** Hit-test reach in px: the largest node shape at the largest radius (a tall rectangle's top or bottom). */
export const NODE_HIT_PX = 14;

function idHash(id: string): number {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** A note's shape from a hash of its id, so it is the same on every draw and every launch. */
export function nodeShape(id: string): number {
  return idHash(id) & 1 ? SHAPE_SQUARE : SHAPE_TALL;
}

/** Outline tones a note can take: the accent, then two lighter tints of it. */
export const TONES = 3;

/** A note's tone from the same id hash, so it is stable across draws and launches. */
export function nodeTone(id: string): number {
  return idHash(id) % TONES;
}

/** Mix an RGBA colour toward white by t (0 to 1), keeping its alpha. */
export function tint([r = 0, g = 0, b = 0, a = 1]: number[], t: number): [number, number, number, number] {
  return [r + (1 - r) * t, g + (1 - g) * t, b + (1 - b) * t, a];
}

export type GraphLayout = "arc" | "force";

/** Round layout: world px between neighbouring notes on the ring, measured along it. */
export const ARC_ROW = 10;
/** Round layout: straight pieces each link curve is drawn with. */
export const ARC_SEGMENTS = 16;
/** Round layout: how far a link's control points sit toward the core, as a share of each end's distance. Under 1 keeps every link a thin curve. */
export const ARC_BEND = 0.5;
/** Round layout: group centres sit this share of the ring's radius out from the core. */
export const ARC_HUB_RADIUS = 0.55;

/** Round layout: the note ring's radius, so neighbours sit about two ARC_ROW apart on it. */
export function ringRadius(count: number): number {
  return Math.max(4 * ARC_ROW, (count * ARC_ROW) / Math.PI);
}

/** Round layout: the angle of row `row` of `count` around the ring, starting at the top. */
function ringAngle(row: number, count: number): number {
  return (row / count) * Math.PI * 2 - Math.PI / 2;
}

/** Round layout: the note ring is centred on the core at (0, 0); node i sits at the angle of rows[i]. */
export function arcLayout(rows: ArrayLike<number>): Float32Array<ArrayBuffer> {
  const count = rows.length;
  const r = ringRadius(count);
  const pos = new Float32Array(count * 2);
  for (let i = 0; i < count; i++) {
    const a = ringAngle(rows[i] ?? 0, count);
    pos[2 * i] = Math.cos(a) * r;
    pos[2 * i + 1] = Math.sin(a) * r;
  }
  return pos;
}

/**
 * Round layout hubs: the note ring, then one centre per group (at the middle of its run, inside the ring), then the core at (0, 0).
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
  const r = ringRadius(count) * ARC_HUB_RADIUS;
  const edges: number[] = [];
  for (let g = 0; g < groups; g++) {
    const a = ringAngle(((lo[g] ?? 0) + (hi[g] ?? 0)) / 2, count);
    const at = 2 * (count + g);
    pos[at] = Math.cos(a) * r;
    pos[at + 1] = Math.sin(a) * r;
    edges.push(count + g, count + groups);
  }
  for (let i = 0; i < count; i++) edges.push(i, count + (of[i] ?? 0));
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
 * The curve is a cubic whose control points are pulled toward the core, so each link bows round it as a thin curve.
 */
export function arcSegments(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  out: Float32Array,
  at: number,
): number {
  const c1x = ax * ARC_BEND;
  const c1y = ay * ARC_BEND;
  const c2x = bx * ARC_BEND;
  const c2y = by * ARC_BEND;
  let px = ax;
  let py = ay;
  for (let s = 1; s <= ARC_SEGMENTS; s++) {
    const t = s / ARC_SEGMENTS;
    const u = 1 - t;
    const x =
      u * u * u * ax + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * bx;
    const y =
      u * u * u * ay + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * by;
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

/** World-space segments for only the links that touch note `focus`, so hovering lights them. Empty for -1. */
export function incidentLines(
  pos: ArrayLike<number>,
  edges: Uint32Array,
  focus: number,
): Float32Array<ArrayBuffer> {
  const picked: number[] = [];
  for (let e = 0; e < edges.length; e += 2)
    if (edges[e] === focus || edges[e + 1] === focus) picked.push(edges[e] ?? 0, edges[e + 1] ?? 0);
  return straightLines(pos, Uint32Array.from(picked));
}
