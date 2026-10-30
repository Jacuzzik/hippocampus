// Tests for ui/graph/model.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  allTags,
  ARC_ROW,
  ARC_SEGMENTS,
  arcCentreX,
  arcHubs,
  arcReach,
  arcLayout,
  arcRows,
  ARC_BOW,
  arcSegments,
  centerOn,
  groupsOf,
  clampZoom,
  hitTest,
  layout,
  linkCounts,
  matchFilter,
  MAX_ZOOM,
  nodeRadius,
  MIN_ZOOM,
  screenToWorld,
  tagCounts,
  zoomAt,
} from "../ui/graph/model.ts";

function syntheticEdges(n, perNode, seed) {
  let s = seed;
  const rand = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  const edges = [];
  for (let i = 0; i < n; i++) {
    for (let k = 0; k < perNode; k++) edges.push([i, Math.floor(rand() * n)]);
  }
  return edges.filter(([a, b]) => a !== b);
}

test("layout is deterministic for a seed and finite for 2,000 nodes", () => {
  const edges = syntheticEdges(2000, 2, 7);
  const t0 = Date.now();
  const a = layout(2000, edges, undefined, 3);
  const elapsed = Date.now() - t0;
  const b = layout(2000, edges, undefined, 3);
  assert.deepEqual(a, b);
  assert.ok(a.every(Number.isFinite));
  assert.ok(elapsed < 5000, `layout took ${elapsed} ms`);
});

test("linked nodes end up closer than unlinked ones", () => {
  // Two cliques of 20 with no link between them.
  const edges = [];
  for (const base of [0, 20]) {
    for (let i = 0; i < 20; i++)
      for (let j = i + 1; j < 20; j++) edges.push([base + i, base + j]);
  }
  const pos = layout(40, edges, { iterations: 300, samples: 40, dprCap: 1 }, 5);
  const d = (a, b) =>
    Math.hypot(pos[2 * a] - pos[2 * b], pos[2 * a + 1] - pos[2 * b + 1]);
  let within = 0;
  let across = 0;
  for (let i = 0; i < 20; i++) {
    within += d(i, (i + 1) % 20) / 20;
    across += d(i, 20 + i) / 20;
  }
  assert.ok(
    within < across,
    `within ${within.toFixed(1)} vs across ${across.toFixed(1)}`,
  );
});

test("zoom stays under the cursor and is clamped", () => {
  const cam = { x: 100, y: 50, zoom: 1 };
  const [wx, wy] = screenToWorld(cam, 300, 200);
  const next = zoomAt(cam, 300, 200, 2);
  assert.deepEqual(screenToWorld(next, 300, 200), [wx, wy]);
  assert.equal(zoomAt(cam, 0, 0, 1e6).zoom, MAX_ZOOM);
  assert.equal(zoomAt(cam, 0, 0, 1e-6).zoom, MIN_ZOOM);
  assert.equal(clampZoom(1), 1);
});

test("centerOn puts the world point in the middle of the canvas", () => {
  const cam = centerOn(10, -4, 2, 800, 600);
  assert.deepEqual(screenToWorld(cam, 400, 300), [10, -4]);
});

test("hitTest returns the nearest node within the radius, or -1", () => {
  const pos = new Float32Array([0, 0, 100, 0]);
  const cam = { x: 0, y: 0, zoom: 1 };
  assert.equal(hitTest(pos, cam, 3, 4, 8), 0);
  assert.equal(hitTest(pos, cam, 96, 0, 8), 1);
  assert.equal(hitTest(pos, cam, 50, 0, 8), -1);
  assert.equal(hitTest(pos, { x: 0, y: 0, zoom: 2 }, 200, 0, 8), 1);
});

test("the memory filter keeps only assistant-created notes", () => {
  const nodes = [
    { id: "a.md", title: "A", tags: [], memory: true },
    { id: "b.md", title: "B", tags: [] },
    { id: "c.md", title: "C", tags: [], memory: false },
  ];
  assert.deepEqual(matchFilter(nodes, { query: "", tag: null, memory: true }), [
    true,
    false,
    false,
  ]);
  assert.deepEqual(
    matchFilter(nodes, { query: "", tag: null, memory: false }),
    [true, true, true],
  );
});

test("filters match title or path, and tag, and combine", () => {
  const nodes = [
    { id: "projects/alpha.md", title: "Alpha", tags: ["idea"] },
    { id: "journal/2026/day.md", title: "Day", tags: ["idea", "todo"] },
    { id: "areas/health.md", title: "Health", tags: [] },
  ];
  assert.deepEqual(matchFilter(nodes, { query: "", tag: null }), [
    true,
    true,
    true,
  ]);
  assert.deepEqual(matchFilter(nodes, { query: " ALPHA ", tag: null }), [
    true,
    false,
    false,
  ]);
  assert.deepEqual(matchFilter(nodes, { query: "journal", tag: null }), [
    false,
    true,
    false,
  ]);
  assert.deepEqual(matchFilter(nodes, { query: "", tag: "idea" }), [
    true,
    true,
    false,
  ]);
  assert.deepEqual(matchFilter(nodes, { query: "day", tag: "todo" }), [
    false,
    true,
    false,
  ]);
  assert.deepEqual(allTags(nodes), ["idea", "todo"]);
});

test("linkCounts counts each node's links and ignores self and unknown links", () => {
  const nodes = [
    { id: "a.md", title: "A", tags: [] },
    { id: "b.md", title: "B", tags: [] },
    { id: "c.md", title: "C", tags: [] },
  ];
  const edges = [
    ["a.md", "b.md"],
    ["b.md", "a.md"],
    ["a.md", "a.md"],
    ["a.md", "gone.md"],
  ];
  assert.deepEqual(linkCounts(nodes, edges), [2, 2, 0]);
});

test("tagCounts gives each tag and its note count, sorted", () => {
  const nodes = [
    { id: "a.md", title: "A", tags: ["idea", "work"] },
    { id: "b.md", title: "B", tags: ["work"] },
    { id: "c.md", title: "C", tags: [] },
  ];
  assert.deepEqual(tagCounts(nodes), [
    ["idea", 1],
    ["work", 2],
  ]);
});

test("nodeRadius grows with the link count, capped, and a selected node is at least 7", () => {
  assert.equal(nodeRadius(0, false), 4);
  assert.ok(nodeRadius(4, false) > nodeRadius(1, false));
  assert.equal(nodeRadius(10000, false), 10);
  assert.equal(nodeRadius(0, true), 7);
  assert.ok(nodeRadius(16, true) >= nodeRadius(16, false));
});

test("arc rows run by group, then title, one row per note", () => {
  const nodes = [
    { id: "b.md", title: "Beta", tags: ["zeta"] },
    { id: "a.md", title: "Alpha", tags: ["zeta"] },
    { id: "Ideas/c.md", title: "Gamma", tags: [] },
  ];
  // Groups sort as "Ideas" (folder), then "zeta" (tag): Gamma, Alpha, Beta.
  assert.deepEqual(arcRows(nodes), [2, 1, 0]);
  const pos = arcLayout(arcRows(nodes));
  assert.deepEqual([...pos], [0, 2 * ARC_ROW, 0, ARC_ROW, 0, 0]);
});

test("groups use the first tag, else the top folder, else Root", () => {
  const nodes = [
    { id: "x.md", title: "X", tags: ["t"] },
    { id: "f/y.md", title: "Y", tags: [] },
    { id: "z.md", title: "Z", tags: [] },
  ];
  const { names, of } = groupsOf(nodes);
  assert.deepEqual(names, ["f", "Root", "t"]);
  assert.deepEqual(of, [2, 0, 1]);
});

test("a blank tag or folder name never makes an unnamed group", () => {
  const nodes = [
    { id: "x.md", title: "X", tags: ["  "] },
    { id: " /y.md", title: "Y", tags: [] },
  ];
  assert.deepEqual(groupsOf(nodes).names, ["Root"]);
});

test("an arc link starts and ends on its nodes and bows left of both", () => {
  const out = new Float32Array(ARC_SEGMENTS * 4);
  const end = arcSegments(0, 0, 0, 100, out, 0);
  assert.equal(end, ARC_SEGMENTS * 4);
  assert.deepEqual([out[0], out[1]], [0, 0]);
  const last = end - 2;
  assert.deepEqual([out[last], out[last + 1]], [0, 100]);
  // The midpoint of a cubic with both controls at -h sits at -0.75h; h is half the span.
  const mid = (ARC_SEGMENTS / 2) * 4 - 2;
  assert.ok(Math.abs(out[mid] - -37.5) < 1e-3, `midpoint x ${out[mid]}`);
  for (let i = 0; i < end; i += 2) assert.ok(out[i] <= 1e-6);
});

test("arc hubs: a centre per group left of the column, the core on the column's middle row, every note strung to its centre", () => {
  // Two groups: notes 0-1 in "A" (rows 0-1), note 2 in "B" (row 2). Note 1 is linked, but every note still gets a string.
  const rows = [0, 1, 2];
  const of = [0, 0, 1];
  const { pos, edges } = arcHubs(rows, of, 2);
  const cx = arcCentreX(3);
  assert.ok(cx < 0);
  assert.equal(pos.length, (3 + 2 + 1) * 2);
  // Centre A sits on the middle of rows 0-1, centre B on row 2; the core is on the column (x = 0) at the middle row.
  assert.equal(pos[6], cx);
  assert.equal(pos[7], 0.5 * ARC_ROW);
  assert.equal(pos[8], cx);
  assert.equal(pos[9], 2 * ARC_ROW);
  assert.equal(pos[10], 0);
  assert.equal(pos[11], ARC_ROW);
  // Strings: centre A to core, centre B to core, then every note to its centre (0 and 1 to A, 2 to B).
  assert.deepEqual([...edges], [3, 5, 4, 5, 0, 3, 1, 3, 2, 4]);
});

test("arc reach covers the group centres and every arc bow", () => {
  for (const n of [3, 50, 2000]) {
    const cx = arcCentreX(n);
    assert.ok(arcReach(n) <= cx, `reach ${arcReach(n)} vs centre ${cx} for ${n}`);
  }
});

test("an arc never bows past ARC_BOW, however far apart its ends, so long links stay thin curves", () => {
  const out = new Float32Array(ARC_SEGMENTS * 4);
  arcSegments(0, 0, 0, 100000, out, 0);
  let min = 0;
  for (let i = 0; i < out.length; i += 2) min = Math.min(min, out[i]);
  assert.ok(min >= -0.75 * ARC_BOW - 1e-3, `deepest x ${min}`);
  assert.ok(arcReach(5000) <= min + 1e-3, `reach ${arcReach(5000)} vs deepest ${min}`);
});
