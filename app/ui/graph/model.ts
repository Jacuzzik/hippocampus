// Pure graph logic: layout, camera, hit testing, filtering. No DOM or WebGL, so it runs under node --test.

export interface GraphNode {
  id: string;
  title: string;
  tags: string[];
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
}

/** Per node: true if it passes the search text and tag filter. An empty filter passes everything. */
export function matchFilter(
  nodes: readonly GraphNode[],
  filter: Filter,
): boolean[] {
  const q = filter.query.trim().toLocaleLowerCase();
  return nodes.map((n) => {
    if (filter.tag && !n.tags.includes(filter.tag)) return false;
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
