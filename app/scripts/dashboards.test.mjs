// Tests for ui/dashboards/model.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  activityTiles,
  githubTiles,
  noteTiles,
  overviewTiles,
  short,
  spendTiles,
  systemTiles,
  taskTiles,
} from "../ui/dashboards/model.ts";

test("numbers are shortened to k and M", () => {
  assert.equal(short(950), "950");
  assert.equal(short(12400), "12.4k");
  assert.equal(short(3_200_000), "3.2M");
});

test("task tiles count each column and mark cards that wait on the user", () => {
  const tiles = taskTiles([
    { status: "todo" },
    { status: "doing" },
    { status: "blocked", waiting: true },
    { status: "done" },
    { status: "done" },
  ]);
  assert.deepEqual(
    tiles.map((tile) => [tile.label, tile.value]),
    [
      ["Todo", "1"],
      ["Doing", "1"],
      ["Blocked", "1"],
      ["Done", "2"],
      ["Waiting on you", "1"],
    ],
  );
  assert.equal(tiles.at(-1).tone, "warn");
  assert.equal(taskTiles([]).at(-1).tone, "plain");
});

test("note tiles count notes, links, notes with no links and the most used tag", () => {
  const tiles = noteTiles({
    nodes: [
      { id: "a", tags: ["idea"] },
      { id: "b", tags: ["idea", "x"] },
      { id: "c", tags: [] },
    ],
    edges: [["a", "b"]],
  });
  assert.deepEqual(
    tiles.map((tile) => tile.value),
    ["3", "1", "1", "2", "#idea"],
  );
  assert.equal(noteTiles({ nodes: [], edges: [] }).at(-1).value, "None");
});

test("system tiles warn at 90 percent, and at 50 percent for swap", () => {
  const tiles = systemTiles({
    cpu: 91,
    ram: 61,
    swap: 55,
    disk: 33,
    disk_free: 120.5,
  });
  assert.deepEqual(
    tiles.map((tile) => tile.tone),
    ["warn", "plain", "warn", "plain", undefined],
  );
  assert.equal(tiles.at(-1).value, "120.5 GB");
});

test("spend tiles put the biggest spender first, with its share", () => {
  const tiles = spendTiles({ kevin: 3000, assistant: 9000 });
  assert.deepEqual(
    tiles.map((tile) => [tile.label, tile.value]),
    [
      ["Tokens today", "12.0k"],
      ["assistant", "9.0k"],
      ["kevin", "3.0k"],
    ],
  );
  assert.equal(tiles[1].note, "75% of today.");
  assert.equal(spendTiles({})[0].value, "0");
});

test("activity tiles count each kind and show the newest time", () => {
  const tiles = activityTiles([
    { ts: "2026-10-27T09:12:04+00:00", kind: "approval" },
    { ts: "2026-10-27T10:00:00+00:00", kind: "tool" },
    { ts: "2026-10-27T08:00:00+00:00", kind: "tool" },
  ]);
  assert.deepEqual(
    tiles.map((tile) => [tile.label, tile.value]),
    [
      ["Events kept", "3"],
      ["tool", "2"],
      ["approval", "1"],
      ["Newest", "2026-10-27 10:00"],
    ],
  );
});

test("the overview counts open tasks and says when the system was not read", () => {
  const tiles = overviewTiles({
    agents: 2,
    tokens: 15400,
    tasks: [{ status: "todo" }, { status: "done" }],
    asks: 1,
    system: null,
  });
  assert.deepEqual(
    tiles.map((tile) => tile.value),
    ["2", "15.4k", "1", "1", "Not read"],
  );
  assert.equal(tiles[3].tone, "warn");
});

test("GitHub tiles show counts, the newest run and the newest titles", () => {
  const found = {
    repo: "a/b",
    pulls: 100,
    drafts: 1,
    issues: 1,
    runs: 3,
    failed_runs: 1,
    running_runs: 0,
    newest_run: { name: "tests", branch: "main", state: "failed" },
    newest_pulls: [{ number: 7, title: "Add dashboards" }],
    newest_issues: [{ number: 3, title: "Graph is slow" }],
    capped: ["pulls"],
  };
  const tiles = githubTiles(found);
  assert.deepEqual(
    tiles.map((tile) => [tile.label, tile.value]),
    [
      ["Open pull requests", "100+"],
      ["Open issues", "1"],
      ["Newest CI run", "failed"],
      ["Failed runs", "1"],
      ["Pull request #7", "Add dashboards"],
      ["Issue #3", "Graph is slow"],
    ],
  );
  assert.equal(tiles[2].tone, "warn");
  assert.equal(githubTiles({ ...found, newest_run: null })[2].value, "None");
});
