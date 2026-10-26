// 2D canvas renderer for the brain graph, used when WebGL 2 is missing (some phone browsers).
// Same methods as BrainRenderer, so the graph component can use either one.
import type { Camera } from "./model";
import type { Rgba } from "./renderer";

const css = (c: Rgba): string =>
  `rgba(${c[0] * 255},${c[1] * 255},${c[2] * 255},${c[3]})`;

export class Canvas2DRenderer {
  private readonly ctx: CanvasRenderingContext2D;
  private pos: Float32Array = new Float32Array(0);
  private edges: Uint32Array = new Uint32Array(0);
  private colors: Float32Array = new Float32Array(0);
  private radii: Float32Array = new Float32Array(0);
  private dpr = 1;

  constructor(private readonly canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D is not available in this window");
    this.ctx = ctx;
  }

  /** `pos` is interleaved x, y per node; `edges` is interleaved node index pairs. */
  setGraph(pos: Float32Array, edges: Uint32Array): void {
    this.edges = edges;
    this.setPositions(pos);
  }

  setPositions(pos: Float32Array): void {
    this.pos = pos;
  }

  /** One radius (CSS px) per node. */
  setRadii(radii: Float32Array): void {
    this.radii = radii;
  }

  /** One RGBA colour (0 to 1) per node, four floats each. */
  setColors(colors: Float32Array): void {
    this.colors = colors;
  }

  resize(cssWidth: number, cssHeight: number, dprCap: number): void {
    this.dpr = Math.min(window.devicePixelRatio || 1, dprCap);
    this.canvas.width = Math.max(1, Math.round(cssWidth * this.dpr));
    this.canvas.height = Math.max(1, Math.round(cssHeight * this.dpr));
  }

  draw(cam: Camera, background: Rgba, edgeColor: Rgba): void {
    const { ctx, pos, edges, colors, radii } = this;
    const width = this.canvas.width / this.dpr;
    const height = this.canvas.height / this.dpr;
    // Work in CSS pixels; the transform maps them to the backing store.
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.fillStyle = css(background);
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = css(edgeColor);
    ctx.beginPath();
    for (let i = 0; i < edges.length; i += 2) {
      const a = (edges[i] ?? 0) * 2;
      const b = (edges[i + 1] ?? 0) * 2;
      ctx.moveTo(
        (pos[a] ?? 0) * cam.zoom + cam.x,
        (pos[a + 1] ?? 0) * cam.zoom + cam.y,
      );
      ctx.lineTo(
        (pos[b] ?? 0) * cam.zoom + cam.x,
        (pos[b + 1] ?? 0) * cam.zoom + cam.y,
      );
    }
    ctx.stroke();

    for (let i = 0; i < radii.length; i++) {
      const c = [0, 1, 2, 3].map((k) => colors[4 * i + k] ?? 0) as Rgba;
      ctx.fillStyle = css(c);
      ctx.beginPath();
      ctx.arc(
        (pos[2 * i] ?? 0) * cam.zoom + cam.x,
        (pos[2 * i + 1] ?? 0) * cam.zoom + cam.y,
        radii[i] ?? 0,
        0,
        Math.PI * 2,
      );
      ctx.fill();
    }
  }

  dispose(): void {
    // Nothing to free: a 2D context holds no GPU objects.
  }
}
