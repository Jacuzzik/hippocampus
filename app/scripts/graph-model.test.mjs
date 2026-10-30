// Tests for ui/graph/model.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  allTags,
  ARC_ROW,
  ARC_SEGMENTS,
  arcHubs,
  arcLayout,
  arcRows,
  ARC_HUB_RADIUS,
  ringRadius,
  arcSegments,
  centerOn,
  groupsOf,
  clampZoom,
  hitTest,
  labelAlpha,
  layout,
  newSim,
  settle,
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

test("1,167 notes spread out: the typical note keeps room for its dot", () => {
  // Regression: with the old 1/d² charge the vault packed into dots about 8 px apart.
  const n = 1167;
  const pos = layout(n, syntheticEdges(n, 2, 11), undefined, 5);
  const nearest = [];
  for (let i = 0; i < n; i++) {
    let best = Infinity;
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      best = Math.min(best, Math.hypot(pos[2 * i] - pos[2 * j], pos[2 * i + 1] - pos[2 * j + 1]));
    }
    nearest.push(best);
  }
  nearest.sort((a, b) => a - b);
  // 12, not 15: the repel softening lets linked clusters sit ~14 px apart. The 8 px regression still fails.
  assert.ok(nearest[n >> 1] >= 12, `median nearest gap ${nearest[n >> 1]} px`);
});

test("unlinked notes scatter irregularly, not on a lattice", () => {
  // Regression: the real vault is 92% unlinked. Without the repel softening they settled into a regular grid (nearest-gap CV 0.22).
  const n = 1175;
  const linked = 95;
  const pairs = [];
  for (let i = 1; i < linked; i++) pairs.push([i, ((i * 7919) % 97) % i]);
  const deg = new Uint32Array(n);
  for (const [a, b] of pairs) (deg[a]++, deg[b]++);
  const pos = layout(n, pairs, undefined, 1);
  assert.ok(pos.every(Number.isFinite));
  const free = [];
  for (let i = 0; i < n; i++) if (deg[i] === 0) free.push(i);
  const gaps = free.map((i) => {
    let best = Infinity;
    for (const j of free)
      if (j !== i) best = Math.min(best, Math.hypot(pos[2 * i] - pos[2 * j], pos[2 * i + 1] - pos[2 * j + 1]));
    return best;
  });
  const mean = gaps.reduce((a, b) => a + b, 0) / gaps.length;
  const sd = Math.sqrt(gaps.reduce((a, b) => a + (b - mean) ** 2, 0) / gaps.length);
  assert.ok(sd / mean >= 0.4, `nearest-gap CV ${(sd / mean).toFixed(3)}`);
});

test("a hub with 30 links does not blow up the layout", () => {
  // Regression: the link force added its full pull to each end, so a hub's 30 links
  // overshot and the vault's positions ran off to Infinity/NaN (88 of 1,175 real notes).
  const hub = Array.from({ length: 30 }, (_, i) => [0, i + 1]);
  const pos = layout(1175, hub, undefined, 1);
  assert.ok(pos.every(Number.isFinite), "positions must stay finite");
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

test("arc rows run by group, then title, one row per note, and each note sits on the ring", () => {
  const nodes = [
    { id: "b.md", title: "Beta", tags: ["zeta"] },
    { id: "a.md", title: "Alpha", tags: ["zeta"] },
    { id: "Ideas/c.md", title: "Gamma", tags: [] },
  ];
  // Groups sort as "Ideas" (folder), then "zeta" (tag): Gamma, Alpha, Beta.
  assert.deepEqual(arcRows(nodes), [2, 1, 0]);
  const pos = arcLayout(arcRows(nodes));
  const r = ringRadius(3);
  for (let i = 0; i < 3; i++)
    assert.ok(Math.abs(Math.hypot(pos[2 * i] ?? 0, pos[2 * i + 1] ?? 0) - r) < 1e-3);
  // Gamma is row 0, so it sits at the top of the ring.
  assert.ok(Math.abs(pos[4] ?? 1) < 1e-3 && Math.abs((pos[5] ?? 0) + r) < 1e-3);
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

test("an arc link starts and ends on its nodes and bows in toward the core", () => {
  const out = new Float32Array(ARC_SEGMENTS * 4);
  const end = arcSegments(100, 0, 0, 100, out, 0);
  assert.equal(end, ARC_SEGMENTS * 4);
  assert.deepEqual([out[0], out[1]], [100, 0]);
  const last = end - 2;
  assert.deepEqual([out[last], out[last + 1]], [0, 100]);
  // Midpoint of the cubic with controls at half each end: (0.3125 * (A + B)), a straight midpoint would be (50, 50).
  const mid = (ARC_SEGMENTS / 2) * 4 - 2;
  assert.ok(Math.abs(out[mid] - 31.25) < 1e-3, `midpoint x ${out[mid]}`);
  assert.ok(Math.abs(out[mid + 1] - 31.25) < 1e-3, `midpoint y ${out[mid + 1]}`);
});

test("round hubs: a centre per group inside the ring, the core at the origin, every note strung to its centre", () => {
  // Two groups: notes 0-1 in "A" (rows 0-1), note 2 in "B" (row 2). Note 1 is linked, but every note still gets a string.
  const rows = [0, 1, 2];
  const of = [0, 0, 1];
  const { pos, edges } = arcHubs(rows, of, 2);
  const r = ringRadius(3) * ARC_HUB_RADIUS;
  assert.equal(pos.length, (3 + 2 + 1) * 2);
  // Centre A sits at the middle of rows 0-1 (upper right), centre B on row 2 (lower left); each is r out from the core.
  assert.ok(Math.abs(Math.hypot(pos[6] ?? 0, pos[7] ?? 0) - r) < 1e-3);
  assert.ok(Math.abs(Math.hypot(pos[8] ?? 0, pos[9] ?? 0) - r) < 1e-3);
  assert.ok((pos[6] ?? 0) > 0 && (pos[7] ?? 0) < 0);
  assert.ok((pos[8] ?? 0) < 0 && (pos[9] ?? 0) > 0);
  assert.deepEqual([pos[10], pos[11]], [0, 0]);
  // Strings: centre A to core, centre B to core, then every note to its centre (0 and 1 to A, 2 to B).
  assert.deepEqual([...edges], [3, 5, 4, 5, 0, 3, 1, 3, 2, 4]);
});

test("an arc link never reaches past its ends, so a long link from the rim stays a thin curve inside the ring", () => {
  const out = new Float32Array(ARC_SEGMENTS * 4);
  arcSegments(500, 0, 0, -300, out, 0);
  let far = 0;
  for (let i = 0; i < out.length; i += 2)
    far = Math.max(far, Math.hypot(out[i] ?? 0, out[i + 1] ?? 0));
  assert.ok(far <= 500 + 1e-3, `farthest point ${far}`);
});

test("a grabbed note stays where it is held while the simulation settles its neighbours", () => {
  const sim = newSim(3, [[0, 1], [1, 2]]);
  sim.grabbed = 0;
  const [x, y] = [sim.pos[0], sim.pos[1]];
  settle(sim, 50);
  assert.deepEqual([sim.pos[0], sim.pos[1]], [x, y]);
});

test("labels fade in from zoom 0.5 to 1", () => {
  assert.equal(labelAlpha(0.4), 0);
  assert.equal(labelAlpha(1), 1);
  assert.ok(Math.abs(labelAlpha(0.75) - 0.5) < 1e-9);
});
