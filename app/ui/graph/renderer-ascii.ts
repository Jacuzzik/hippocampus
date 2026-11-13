// The ASCII look for the brain graph, drawn on a 2D canvas in world space: "%" cores, "+" bodies, links as "+" runs.
import { fontToken } from "../cssToken.ts";
import { ballCells, cellOf, CELL, CELL_H, HUB_DEG } from "./ascii-model.ts";

/** Opacity of the notes and links that are not focused (hovered, else selected). */
const DIM = 0.35;
import type { Camera } from "./model";

export interface AsciiColours {
  bg: string;
  node: string;
  link: string;
  hub: string;
}

/**
 * Paints the whole picture. `pos` is the note positions (core last), `edges` the flat index pairs, `t` the time in
 * seconds. `focus` is the hovered (else selected) note, or -1: it and its links stay full strength, the rest dim.
 */
export function drawAscii(
  ctx: CanvasRenderingContext2D,
  cam: Camera,
  pos: ArrayLike<number>,
  edges: Uint32Array,
  deg: ArrayLike<number>,
  colours: AsciiColours,
  width: number,
  height: number,
  t: number,
  focus: number,
): void {
  const z = cam.zoom;
  ctx.globalAlpha = 1;
  ctx.fillStyle = colours.bg;
  ctx.fillRect(0, 0, width, height);
  ctx.font = `bold ${CELL * z * 1.3}px ${fontToken("mono")}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  // Cell of a note at time t: its world position in cells, plus its orbit, so every glyph sits on the grid.
  const cell = (i: number) =>
    cellOf(i, pos[2 * i] ?? 0, pos[2 * i + 1] ?? 0, t);
  const sx = (c: number) => c * CELL * z + cam.x;
  const sy = (r: number) => r * CELL_H * z + cam.y;

  for (let e = 0; e < edges.length; e += 2) {
    const a = edges[e] ?? 0;
    const b = edges[e + 1] ?? 0;
    const [ca, ra] = cell(a);
    const [cb, rb] = cell(b);
    // About 70% of hub-to-hub links (7 in every 10) use the darker colour.
    const hub =
      (deg[a] ?? 0) >= HUB_DEG && (deg[b] ?? 0) >= HUB_DEG && (e / 2) % 10 < 7;
    ctx.fillStyle = hub ? colours.hub : colours.link;
    ctx.globalAlpha = focus < 0 || a === focus || b === focus ? 1 : DIM;
    const len = Math.max(Math.abs(cb - ca), Math.abs(rb - ra), 1);
    for (let t = 0; t <= len; t++) {
      // Per cell: 40% a small dot, 60% blank, like the reference's dotted links. A fixed hash, so the picture does not flicker.
      const roll =
        ((Math.imul(t + 1, 7919) ^
          Math.imul(ca + 3, 104729) ^
          Math.imul(ra + 5, 1299709) ^
          Math.imul(e + 7, 2246822519)) >>>
          0) %
        10;
      if (roll >= 4) continue;
      const ch = "·";
      ctx.fillText(
        ch,
        sx(Math.round(ca + ((cb - ca) * t) / len)),
        sy(Math.round(ra + ((rb - ra) * t) / len)),
      );
    }
  }

  // Notes last, so they win over the links that run into them.
  ctx.fillStyle = colours.node;
  for (let i = 0; i < deg.length; i++) {
    ctx.globalAlpha = focus < 0 || i === focus ? 1 : DIM;
    const [c, r] = cell(i);
    for (const [dx, dy, ch] of ballCells(deg[i] ?? 0))
      ctx.fillText(ch, sx(c + dx), sy(r + dy));
  }
}
