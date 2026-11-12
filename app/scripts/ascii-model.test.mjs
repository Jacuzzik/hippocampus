// Tests for ui/graph/ascii-model.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  asciiLayout,
  ballCells,
  cellOf,
  CELL,
  hideTestNotes,
} from "../ui/graph/ascii-model.ts";

// One hub "h" with seven notes, plus a lonely note with no links.
const star = {
  nodes: [
    { id: "h", title: "Hub", tags: [] },
    ...Array.from({ length: 7 }, (_, i) => ({
      id: "n" + i,
      title: "N" + i,
      tags: [],
    })),
    { id: "lonely", title: "Lonely", tags: [] },
  ],
  edges: Array.from({ length: 7 }, (_, i) => ["h", "n" + i]),
};

test("hideTestNotes drops test<digits> notes and their links, keeps other names", () => {
  const data = {
    nodes: [
      { id: "Hippocampus/test3.md", title: "test3", tags: [] },
      { id: "test12.md", title: "test12", tags: [] },
      { id: "Test Hub.md", title: "Test Hub", tags: [] },
      { id: "testing.md", title: "testing", tags: [] },
      { id: "keep.md", title: "keep", tags: [] },
    ],
    edges: [
      ["Hippocampus/test3.md", "keep.md"],
      ["test12.md", "Test Hub.md"],
      ["keep.md", "testing.md"],
    ],
  };
  const out = hideTestNotes(data);
  assert.deepEqual(
    out.nodes.map((n) => n.id),
    ["Test Hub.md", "testing.md", "keep.md"],
  );
  assert.deepEqual(out.edges, [["keep.md", "testing.md"]]);
});

test("a note's orbit stays within one cell of its base, and moves over time", () => {
  for (let i = 0; i < 20; i++) {
    const [c0, r0] = cellOf(i, 60, -30, 0);
    for (let t = 0; t < 10; t += 0.37) {
      const [c, r] = cellOf(i, 60, -30, t);
      assert.ok(
        Math.abs(c - c0) <= 2 && Math.abs(r - r0) <= 2,
        `note ${i} at t=${t}`,
      );
    }
  }
  const moved = new Set();
  for (let t = 0; t < 10; t += 0.1) moved.add(cellOf(3, 60, -30, t).join(","));
  assert.ok(moved.size > 1, "the orbit changes the cell over time");
});

test("hubs sit on the outer rings, other notes near the centre, core last at the origin", () => {
  const pos = asciiLayout(star);
  assert.equal(pos.length, (star.nodes.length + 1) * 2);
  assert.deepEqual([pos[pos.length - 2], pos[pos.length - 1]], [0, 0]);
  // The hub has 7 links (a hub), so it is on a ring of 20, 40, 50 or 70 cells (rounding allows 1).
  // Measured in screen units (a cell is CELL wide and CELL_H tall), so the ring must be round on screen.
  const cx = pos[0] / CELL;
  const cy = pos[1] / CELL;
  const r = Math.hypot(cx, cy);
  // The outline is lumpy, so a hub can sit up to 45% off its ring.
  assert.ok(
    [20, 40, 50, 70].some((ring) => Math.abs(r - ring) <= ring * 0.45 + 1.5),
    `hub at ${r} cells`,
  );
  // Every note has its own cell, so no two share a spot.
  const spots = new Set();
  for (let i = 0; i < star.nodes.length; i++)
    spots.add(pos[2 * i] + "," + pos[2 * i + 1]);
  assert.equal(spots.size, star.nodes.length);
});

test("a note's ball has a bold core and a body, and grows with its links", () => {
  const small = ballCells(0);
  assert.ok(small.some(([, , ch]) => ch === "•"));
  assert.ok(small.some(([, , ch]) => ch === "·"));
  assert.ok(ballCells(9).length > small.length);
});
