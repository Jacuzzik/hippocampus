// Neural constellation: the geometry of the hybrid ASCII + holographic look. Pure, no DOM, so it runs under node --test.
// Built from the real vault graph and its force layout positions; the same ids always give the same picture.
import { linkCounts, type GraphData } from "./model.ts";

/** Links a note needs to count as a hub (a bright dense formation). Notes under it are small formations. */
export const HUB_LINKS = 6;
/** The glyphs: 0 "·" faint dot, 1 "+" mark, 2 "%" bold mark. */
export const GLYPH_CHARS = ["·", "+", "%"] as const;
/** Colours are indexes into the holo-0 to holo-7 tokens in design/tokens.json: 0 white, then the holographic palette from the brief. */
export const PALETTE_SIZE = 8;
const WHITE = 0;
const VIOLET = 1;
const PURPLE = 2;
const MAGENTA = 3;
const CYAN = 4;
const BLUE = 5;
const HUB_COLOURS = [VIOLET, PURPLE, MAGENTA, BLUE];
/** Most particles drawn along one connection, so a long link cannot flood the picture. */
const MAX_PARTICLES = 60;

/** Flat arrays for speed. Glyph: x, y, char, colour, alpha, owner. Box: x, y, w, h, colour, alpha, owner. */
export const GLYPH_STRIDE = 6;
export const BOX_STRIDE = 7;
/** owner = node index * 2 for a note, edge index * 2 + 1 for a connection. */
export interface Constellation {
  glyphs: Float32Array;
  boxes: Float32Array;
  /** Node index pair for each edge index, so a connection can be lit with its ends. */
  ends: Int32Array;
}

/** A stream seeded from a string (FNV-1a), so a formation depends only on its own id. */
export function rng(seed: string): () => number {
  let s = 2166136261;
  for (let k = 0; k < seed.length; k++) s = Math.imul(s ^ seed.charCodeAt(k), 16777619) >>> 0;
  return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296);
}

/**
 * Display-only test set: 12 hubs, 60 notes linked to them (5 each), and 140 lonely notes. The vault is not changed.
 * Hubs link in a ring so they form a web and do not pull apart.
 */
export function withTestGraph(data: GraphData): GraphData {
  const nodes = [...data.nodes];
  const edges: [string, string][] = [...data.edges];
  const hubs = Array.from({ length: 12 }, (_, i) => "test-hub-" + i);
  hubs.forEach((id) => nodes.push({ id, title: id, tags: [] }));
  hubs.forEach((h, i) => edges.push([h, (hubs[(i + 1) % hubs.length] ?? h)]));
  for (let i = 0; i < 60; i++) {
    const id = "test-note-" + i;
    nodes.push({ id, title: id, tags: [] });
    edges.push([id, (hubs[i % hubs.length] ?? hubs[0] ?? id)]);
  }
  for (let i = 0; i < 140; i++) nodes.push({ id: "test-lonely-" + i, title: "test-lonely-" + i, tags: [] });
  return { nodes, edges };
}

/**
 * Builds every glyph and box from the node positions. `pos` is the force layout (x, y pairs in node order).
 * Hubs get a dense core and nested towers; notes get small formations in their hub's colour; edges become
 * curved trails of sparse dots with an occasional tiny box; lonely notes stay alone, with no trail.
 */
export function buildConstellation(data: GraphData, pos: ArrayLike<number>): Constellation {
  const n = data.nodes.length;
  const deg = linkCounts(data.nodes, data.edges);
  const index = new Map(data.nodes.map((node, i) => [node.id, i]));
  const isHub = data.nodes.map((node, i) => (deg[i] ?? 0) >= HUB_LINKS || node.id.startsWith("hub:") || node.title === "MAIN");

  // Each note takes the colour of a hub it links to; a hub takes one from its id.
  const colour = new Int32Array(n).fill(CYAN);
  const ownerHub = new Int32Array(n).fill(-1);
  for (let i = 0; i < n; i++) if (isHub[i]) colour[i] = HUB_COLOURS[Math.floor(rng(data.nodes[i]?.id ?? "")() * HUB_COLOURS.length)] ?? CYAN;
  const ends = new Int32Array(2 * data.edges.length);
  data.edges.forEach(([a, b], e) => {
    const ia = index.get(a);
    const ib = index.get(b);
    ends[2 * e] = ia ?? -1;
    ends[2 * e + 1] = ib ?? -1;
    if (ia === undefined || ib === undefined || ia === ib) return;
    if (isHub[ib] && (ownerHub[ia] ?? -1) < 0) ownerHub[ia] = ib;
    if (isHub[ia] && (ownerHub[ib] ?? -1) < 0) ownerHub[ib] = ia;
  });
  for (let i = 0; i < n; i++) {
    const hub = ownerHub[i] ?? -1;
    if (!isHub[i] && hub >= 0) colour[i] = colour[hub] ?? CYAN;
  }

  const glyphs: number[] = [];
  const boxes: number[] = [];
  const glyph = (x: number, y: number, ch: number, c: number, a: number, owner: number) =>
    glyphs.push(x, y, ch, c, a, owner);
  const box = (x: number, y: number, w: number, h: number, c: number, a: number, owner: number) =>
    boxes.push(x, y, w, h, c, a, owner);

  // Connections first, so the formations sit on top of their trails.
  data.edges.forEach(([a, b], e) => {
    const ia = ends[2 * e] ?? -1;
    const ib = ends[2 * e + 1] ?? -1;
    if (ia < 0 || ib < 0 || ia === ib) return;
    const x0 = pos[2 * ia] ?? 0;
    const y0 = pos[2 * ia + 1] ?? 0;
    const x1 = pos[2 * ib] ?? 0;
    const y1 = pos[2 * ib + 1] ?? 0;
    const len = Math.hypot(x1 - x0, y1 - y0);
    if (len < 1) return;
    const r = rng(a + "|" + b);
    // A bent control point makes the trail curve; the bend and density differ per edge.
    const bend = (r() - 0.5) * 0.5;
    const cx = (x0 + x1) / 2 - (y1 - y0) * bend;
    const cy = (y0 + y1) / 2 + (x1 - x0) * bend;
    const step = 3 + r() * 2;
    const steps = Math.min(MAX_PARTICLES, Math.floor(len / step));
    const keep = 0.55 + r() * 0.4;
    const hubPair = isHub[ia] && isHub[ib];
    const owner = e * 2 + 1;
    for (let k = 1; k < steps; k++) {
      // Irregular spacing: each particle jitters off its even slot along the curve.
      const t = Math.min(1, Math.max(0, k / steps + ((r() - 0.5) * 0.4) / steps));
      if (r() > keep) continue;
      const u = 1 - t;
      const x = u * u * x0 + 2 * u * t * cx + t * t * x1;
      const y = u * u * y0 + 2 * u * t * cy + t * t * y1;
      if (hubPair && k % 9 === 0) box(x, y, 3, 2, (colour[ia] ?? CYAN), 0.5, owner);
      else glyph(x, y, r() < 0.7 ? 0 : 1, WHITE, 0.28 + 0.2 * r(), owner);
    }
  });

  for (let i = 0; i < n; i++) {
    const r = rng(data.nodes[i]?.id ?? "");
    const x = pos[2 * i] ?? 0;
    const y = pos[2 * i + 1] ?? 0;
    const own = i * 2;
    const d = deg[i] ?? 0;
    if (isHub[i]) {
      // Dense core: a bold % centre, then + marks that thin out towards the edge.
      const R = 7 + 2.2 * Math.sqrt(d);
      const count = Math.min(90, 12 + 3 * d);
      glyph(x, y, 2, WHITE, 1, own);
      for (let k = 0; k < count; k++) {
        const rad = R * r() * r();
        const a = r() * Math.PI * 2;
        const bright = k % 7 === 0;
        glyph(x + Math.cos(a) * rad, y + Math.sin(a) * rad, rad < R * 0.3 ? 2 : 1, bright ? WHITE : (colour[i] ?? CYAN), 1 - (0.7 * rad) / R, own);
      }
      // Nested towers: tall or wide outlined boxes around the core, with a white crossing at the corner.
      const towers = 2 + Math.min(4, Math.floor(d / 3));
      for (let b = 0; b < towers; b++) {
        const w = R * (0.5 + 0.6 * r());
        const h = r() < 0.5 ? w * (1.6 + 0.8 * r()) : w * (0.5 + 0.4 * r());
        const bx = x + (r() - 0.5) * R * 0.6 - w / 2;
        const by = y + (r() - 0.5) * R * 0.6 - h / 2;
        box(bx, by, w, h, (colour[i] ?? CYAN), 0.55, own);
        glyph(bx, by, 1, WHITE, 1, own);
      }
    } else if (d === 0) {
      // Lonely note: its own small mark, never joined to anything.
      const pick = r();
      if (pick < 0.4) glyph(x, y, 1, WHITE, 0.45, own);
      else if (pick < 0.7) glyph(x, y, 2, WHITE, 0.4, own);
      else box(x - 1.5, y - 2, 3, 4, WHITE, 0.35, own);
    } else {
      // Note with links: a small outlined box, or a few + marks, in its hub's colour.
      if (r() < 0.35) box(x - 1.3, y - 2, 2.6, 4.2, (colour[i] ?? CYAN), 0.6, own);
      else {
        const m = 3 + Math.floor(r() * 3);
        for (let k = 0; k < m; k++) {
          const a = r() * Math.PI * 2;
          const rad = 2.5 * r();
          glyph(x + Math.cos(a) * rad, y + Math.sin(a) * rad, 1, r() < 0.2 ? WHITE : (colour[i] ?? CYAN), 0.75, own);
        }
      }
    }
  }

  return { glyphs: Float32Array.from(glyphs), boxes: Float32Array.from(boxes), ends };
}
