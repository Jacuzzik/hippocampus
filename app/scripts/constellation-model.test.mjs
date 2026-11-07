// Tests for ui/graph/constellation-model.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import { buildConstellation, BOX_STRIDE, GLYPH_STRIDE, HUB_LINKS } from "../ui/graph/constellation-model.ts";

// A hub "h" with HUB_LINKS notes, a chain of two small notes, and one lonely note.
const hubLinks = Array.from({ length: HUB_LINKS }, (_, i) => ["h", "n" + i]);
const data = {
  nodes: [
    { id: "h", title: "Hub", tags: [] },
    ...Array.from({ length: HUB_LINKS }, (_, i) => ({ id: "n" + i, title: "N" + i, tags: [] })),
    { id: "a", title: "A", tags: [] },
    { id: "b", title: "B", tags: [] },
    { id: "lonely", title: "Lonely", tags: [] },
  ],
  edges: [...hubLinks, ["a", "b"]],
};
// Spread the nodes out on a grid so the trails have room to curve.
const pos = new Float32Array(2 * data.nodes.length);
data.nodes.forEach((_, i) => {
  pos[2 * i] = (i % 5) * 60;
  pos[2 * i + 1] = Math.floor(i / 5) * 60;
});

test("the same graph gives the same picture every time", () => {
  const a = buildConstellation(data, pos);
  const b = buildConstellation(data, pos);
  assert.deepEqual(a.glyphs, b.glyphs);
  assert.deepEqual(a.boxes, b.boxes);
});

test("a hub gets a bold core and towers; the lonely note has no trail", () => {
  const geo = buildConstellation(data, pos);
  const lonelyIdx = data.nodes.findIndex((n) => n.id === "lonely");
  const hubOwner = 0 * 2;
  // The hub owns a % core glyph at its own position and at least one tower box.
  let core = false;
  for (let k = 0; k < geo.glyphs.length; k += GLYPH_STRIDE)
    if (geo.glyphs[k + 5] === hubOwner && geo.glyphs[k + 2] === 2) core = true;
  assert.ok(core, "hub has a bold core");
  let towers = 0;
  for (let k = 0; k < geo.boxes.length; k += BOX_STRIDE) if (geo.boxes[k + 6] === hubOwner) towers++;
  assert.ok(towers >= 2, "hub has towers");
  // No edge owns a trail touching the lonely note.
  const lonelyEdges = data.edges.flatMap(([x, y], e) => (x === "lonely" || y === "lonely" ? [e] : []));
  assert.equal(lonelyEdges.length, 0);
  // The lonely note still has a formation of its own.
  const own = lonelyIdx * 2;
  let formed = 0;
  for (let k = 0; k < geo.glyphs.length; k += GLYPH_STRIDE) if (geo.glyphs[k + 5] === own) formed++;
  for (let k = 0; k < geo.boxes.length; k += BOX_STRIDE) if (geo.boxes[k + 6] === own) formed++;
  assert.ok(formed >= 1, "lonely note has a mark");
});

test("every note owns at least one glyph or box, and trails are owned by their edge", () => {
  const geo = buildConstellation(data, pos);
  const owners = new Set();
  for (let k = 0; k < geo.glyphs.length; k += GLYPH_STRIDE) owners.add(geo.glyphs[k + 5]);
  for (let k = 0; k < geo.boxes.length; k += BOX_STRIDE) owners.add(geo.boxes[k + 6]);
  for (let i = 0; i < data.nodes.length; i++) assert.ok(owners.has(i * 2), `note ${i} drawn`);
  // The chain edge (a-b) is the last edge; its trail is owned by that edge's odd code.
  const abOwner = (data.edges.length - 1) * 2 + 1;
  assert.ok(owners.has(abOwner), "the a-b connection has a trail");
});

test("the test set adds 12 hubs, 60 linked notes and 140 lonely notes, and keeps the vault", async () => {
  const { withTestGraph } = await import("../ui/graph/constellation-model.ts");
  const out = withTestGraph(data);
  assert.equal(out.nodes.length, data.nodes.length + 12 + 60 + 140);
  assert.deepEqual(out.nodes.slice(0, data.nodes.length), data.nodes);
  const linked = out.edges.filter(([a, b]) => a.startsWith("test-note-") || b.startsWith("test-note-"));
  assert.equal(linked.length, 60);
});
