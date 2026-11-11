// Paints the neural constellation on a 2D canvas: black void, dots and marks, outlined boxes. Culled to the view.
import type { Camera } from "./model.ts";
import { BOX_STRIDE, GLYPH_STRIDE, PALETTE_SIZE, type Constellation } from "./constellation-model.ts";
import { cssToken } from "../cssToken.ts";

// The palette is read from the colour tokens once, on the first draw.
let palette: string[] | null = null;
function colours(): string[] {
  palette ??= Array.from({ length: PALETTE_SIZE }, (_, i) => cssToken(`holo-${i}`));
  return palette;
}

/** Dims everything that is not lit (the focus and its links) to this alpha. */
const DIM = 0.16;

/**
 * Draws the picture. `lit` marks the note in focus and its neighbours (one byte per note); null means nothing is in focus.
 * Connections count as lit when either end is lit.
 */
export function drawConstellation(
  ctx: CanvasRenderingContext2D,
  cam: Camera,
  geo: Constellation,
  w: number,
  h: number,
  lit: Uint8Array | null,
): void {
  const PALETTE = colours();
  const white = PALETTE[0] ?? "";
  ctx.fillStyle = cssToken("void");
  ctx.fillRect(0, 0, w, h);
  const z = cam.zoom;
  const isLit = (owner: number): boolean => {
    if (!lit) return true;
    if (owner % 2 === 0) return lit[owner / 2] === 1;
    const e = (owner - 1) / 2;
    return lit[geo.ends[2 * e] ?? -1] === 1 || lit[geo.ends[2 * e + 1] ?? -1] === 1;
  };
  const visibleRect = (x: number, y: number, pad: number) => x >= -pad && y >= -pad && x <= w + pad && y <= h + pad;

  // Boxes: outlined only, skipped when they would be sub-pixel.
  ctx.lineWidth = 1;
  const boxes = geo.boxes;
  for (let k = 0; k < boxes.length; k += BOX_STRIDE) {
    const sw = (boxes[k + 2] ?? 0) * z;
    const sh = (boxes[k + 3] ?? 0) * z;
    if (sw < 1.5 && sh < 1.5) continue;
    const sx = (boxes[k] ?? 0) * z + cam.x;
    const sy = (boxes[k + 1] ?? 0) * z + cam.y;
    if (sx + sw < 0 || sy + sh < 0 || sx > w || sy > h) continue;
    const owner = boxes[k + 6] ?? 0;
    ctx.globalAlpha = (boxes[k + 5] ?? 0) * (isLit(owner) ? 1 : DIM);
    ctx.strokeStyle = PALETTE[boxes[k + 4] ?? 0] ?? white;
    ctx.strokeRect(sx, sy, Math.max(sw, 1), Math.max(sh, 1));
  }

  // Marks are drawn as shapes, not text: 0 a dot, 1 a small cross, 2 a filled square. Thinned when zoomed far out.
  const g = geo.glyphs;
  const thin = z < 0.25;
  for (let k = 0; k < g.length; k += GLYPH_STRIDE) {
    if (thin && (k / GLYPH_STRIDE) % 3 !== 0) continue;
    const sx = (g[k] ?? 0) * z + cam.x;
    const sy = (g[k + 1] ?? 0) * z + cam.y;
    if (!visibleRect(sx, sy, 8)) continue;
    const owner = g[k + 5] ?? 0;
    const kind = g[k + 2] ?? 0;
    ctx.globalAlpha = (g[k + 4] ?? 0) * (isLit(owner) ? 1 : DIM);
    ctx.fillStyle = PALETTE[g[k + 3] ?? 0] ?? white;
    ctx.strokeStyle = ctx.fillStyle;
    if (kind === 0) {
      ctx.beginPath();
      ctx.arc(sx, sy, Math.max(0.6, 0.9 * z), 0, Math.PI * 2);
      ctx.fill();
    } else if (kind === 1) {
      const r = Math.max(1.5, 2.2 * z);
      ctx.beginPath();
      ctx.moveTo(sx - r, sy);
      ctx.lineTo(sx + r, sy);
      ctx.moveTo(sx, sy - r);
      ctx.lineTo(sx, sy + r);
      ctx.stroke();
    } else {
      const s = Math.max(1.5, 2.6 * z);
      ctx.fillRect(sx - s / 2, sy - s / 2, s, s);
    }
  }
  ctx.globalAlpha = 1;
}
