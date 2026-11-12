// ASCII look for the brain graph: ring placement, the test data and the glyph rules. No DOM, so it runs under node --test.
import { linkCounts, type GraphData } from "./model.ts";

/** Notes with this many links or more are hubs: they sit on the outer rings. */
export const HUB_DEG = 6;
/** One picture cell in world units: CELL wide, CELL_H tall. A character cell is about twice as tall as wide. */
export const CELL = 6;
export const CELL_H = 9;
const HUB_RADII = [20, 40, 50, 70];
const NOTE_RADII = [5, 10, 7, 9, 14];

/** Drops the vault's test<digits> notes (data/brains/Hippocampus/test*.md) from the graph view. The files stay. */
export function hideTestNotes(data: GraphData): GraphData {
  const gone = new Set(
    data.nodes
      .filter((n) =>
        /^test\d+$/.test((n.id.split("/").pop() ?? "").replace(/\.md$/i, "")),
      )
      .map((n) => n.id),
  );
  if (gone.size === 0) return data;
  return {
    nodes: data.nodes.filter((n) => !gone.has(n.id)),
    edges: data.edges.filter(([a, b]) => !gone.has(a) && !gone.has(b)),
  };
}

/** Radius multiplier by angle: 0.55 to 1.45, lumpy so no layout is a perfect circle. */
const lump = (a: number) =>
  1 + 0.3 * Math.sin(3 * a + 0.7) + 0.15 * Math.sin(5 * a + 2.1);

/** A random stream seeded from a note id (FNV-1a hash), so a note's spot depends only on its own id. */
function idRandom(id: string): () => number {
  let s = 2166136261;
  for (let k = 0; k < id.length; k++)
    s = Math.imul(s ^ id.charCodeAt(k), 16777619) >>> 0;
  return () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296;
}

/**
 * World positions for every note, in the order of data.nodes, then the core at the origin (the same
 * shape as the force layout's pos). Hubs go on the outer rings, other notes near the centre.
 */
export function asciiLayout(data: GraphData): Float32Array<ArrayBuffer> {
  const deg = linkCounts(data.nodes, data.edges);
  const out = new Float32Array((data.nodes.length + 1) * 2);
  const taken = new Set<string>();
  // With 40+ hubs they scatter over a disc like planets; fewer keep to the rings.
  const hubs = data.nodes.filter((_, i) => (deg[i] ?? 0) >= HUB_DEG).length;
  const scatter = hubs > 40;
  const disc = 20 + 6 * Math.sqrt(hubs);
  data.nodes.forEach((node, i) => {
    // Each note draws from its own stream seeded by its id, so adding a note does not move the others.
    const random = idRandom(node.id);
    const hub = (deg[i] ?? 0) >= HUB_DEG;
    const choices = hub ? HUB_RADII : NOTE_RADII;
    let rad = choices[Math.floor(random() * choices.length)] ?? 5;
    // When a ring has no free cell left, the next ring out is used, so placement always finishes.
    for (;;) {
      let placed = false;
      for (let tries = 0; tries < 64 && !placed; tries++) {
        const a = random() * Math.PI * 2;
        // In scatter mode every note spreads over the disc, not just the hubs, and the middle third is kept clear.
        // Every layout has a lumpy outline, not a circle, so the picture reads as organic like the reference.
        const R = (scatter ? disc : rad) * lump(a);
        const hole = R * 0.35;
        const dist = scatter
          ? Math.sqrt(hole * hole + random() * (R * R - hole * hole))
          : R;
        const c = Math.round(Math.cos(a) * dist);
        // Rows are CELL_H tall, so the row count is squashed by CELL / CELL_H to keep the ring round on screen.
        const r = Math.round((Math.sin(a) * dist * CELL) / CELL_H);
        const key = c + "," + r;
        if (taken.has(key)) continue;
        taken.add(key);
        out[2 * i] = c * CELL;
        out[2 * i + 1] = r * CELL_H;
        placed = true;
      }
      if (placed) break;
      rad += 1;
    }
  });
  return out;
}

/**
 * The cell a note is drawn in at time t (seconds): its base cell plus a one-cell orbit. Each note has its
 * own speed and phase, so the picture breathes.
 * shortcut: whole-cell steps only, so the orbit is ASCII-sized, upgrade to sub-cell offsets if it looks steppy.
 */
export function cellOf(
  i: number,
  x: number,
  y: number,
  t: number,
): [number, number] {
  const c = Math.round(x / CELL);
  const r = Math.round(y / CELL_H);
  const a = t * (0.3 + (i % 7) * 0.05) + i * 2.399;
  return [c + Math.round(Math.cos(a)), r + Math.round(Math.sin(a) * 0.6)];
}

/** A ball of glyphs: a bold "%" core, then "+" body that fades to the edge. Radius grows with links. */
export function ballCells(deg: number): [number, number, string][] {
  const r = Math.min(deg >= HUB_DEG ? 3 : 2, 1 + Math.floor(deg / 3));
  // Rows are about twice as tall as columns, so hubs stretch the row distance to look round on screen.
  // Rows are 9px and columns 6px, so 2.25 (= (9/6)^2) makes the ball round on screen.
  const squash = 2.25;
  const R = Math.ceil(r * 1.3);
  const out: [number, number, string][] = [];
  for (let dy = -R; dy <= R; dy++)
    for (let dx = -R; dx <= R; dx++) {
      // Round outline for every note (no lumpy edge): the bold core and the body are both circles.
      const wob = 1;
      const d = Math.sqrt(dx * dx + dy * dy * squash);
      if (d <= r * 0.45) out.push([dx, dy, "•"]);
      else if (d <= r * wob) out.push([dx, dy, "·"]);
    }
  return out;
}
