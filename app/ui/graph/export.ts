// The graph as an SVG picture: every note as a circle with its name, every link as a line.
// Built from the note positions alone, so it needs no canvas and gives the same picture each time.

export type ExportColours = {
  bg: string;
  node: string;
  edge: string;
  text: string;
};

const MARGIN = 40;
const RADIUS = 5;

function escape(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/** `pos` holds x, y for each note in order; `edges` holds pairs of note numbers. */
export function graphSvg(
  titles: readonly string[],
  pos: ArrayLike<number>,
  edges: ArrayLike<number>,
  colours: ExportColours,
): string {
  const count = titles.length;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (let i = 0; i < count; i++) {
    const x = pos[2 * i] ?? 0;
    const y = pos[2 * i + 1] ?? 0;
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  if (count === 0) minX = minY = maxX = maxY = 0;
  const width = Math.ceil(maxX - minX + 2 * MARGIN);
  const height = Math.ceil(maxY - minY + 2 * MARGIN);
  const at = (i: number): [string, string] => [
    ((pos[2 * i] ?? 0) - minX + MARGIN).toFixed(1),
    ((pos[2 * i + 1] ?? 0) - minY + MARGIN).toFixed(1),
  ];
  const lines: string[] = [];
  for (let e = 0; e + 1 < edges.length; e += 2) {
    const a = edges[e] ?? 0;
    const b = edges[e + 1] ?? 0;
    if (a >= count || b >= count) continue;
    const [x1, y1] = at(a);
    const [x2, y2] = at(b);
    lines.push(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`);
  }
  const dots: string[] = [];
  const names: string[] = [];
  titles.forEach((title, i) => {
    const [x, y] = at(i);
    dots.push(`<circle cx="${x}" cy="${y}" r="${RADIUS}"/>`);
    names.push(
      `<text x="${x}" y="${(Number(y) + RADIUS + 12).toFixed(1)}">${escape(title)}</text>`,
    );
  });
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    `<rect width="100%" height="100%" fill="${escape(colours.bg)}"/>`,
    `<g stroke="${escape(colours.edge)}" stroke-width="1">${lines.join("")}</g>`,
    `<g fill="${escape(colours.node)}">${dots.join("")}</g>`,
    `<g fill="${escape(colours.text)}" font-size="10" text-anchor="middle">${names.join("")}</g>`,
    "</svg>",
  ].join("\n");
}

/** A saved place in the graph: where the view was and how far it was zoomed. */
export type SavedView = { name: string; x: number; y: number; zoom: number };
export const MAX_VIEWS = 9;

/** Adds the current view under the next free name ("View 1", "View 2", ...). The oldest goes when the list is full. */
export function addView(
  views: readonly SavedView[],
  cam: { x: number; y: number; zoom: number },
): SavedView[] {
  const used = new Set(views.map((view) => view.name));
  let n = 1;
  while (used.has(`View ${n}`)) n++;
  return [
    ...views,
    { name: `View ${n}`, x: cam.x, y: cam.y, zoom: cam.zoom },
  ].slice(-MAX_VIEWS);
}

/** Reads saved views from stored text; anything that is not a list of views gives an empty list. */
export function parseViews(text: string | null): SavedView[] {
  try {
    const found: unknown = JSON.parse(text ?? "[]");
    if (!Array.isArray(found)) return [];
    return found
      .filter(
        (v): v is SavedView =>
          typeof v?.name === "string" &&
          [v.x, v.y, v.zoom].every((n) => Number.isFinite(n)) &&
          v.zoom > 0,
      )
      .slice(-MAX_VIEWS);
  } catch {
    return [];
  }
}
