// Tests for ui/graph/export.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  addView,
  graphSvg,
  MAX_VIEWS,
  parseViews,
} from "../ui/graph/export.ts";

const colours = { bg: "#000", node: "#fff", edge: "#888", text: "#eee" };

test("the picture has one circle and one name per note and one line per link", () => {
  const svg = graphSvg(
    ["Alpha", "Beta", "Gamma"],
    [0, 0, 100, 0, 50, 80],
    [0, 1, 1, 2],
    colours,
  );
  assert.equal((svg.match(/<circle /g) ?? []).length, 3);
  assert.equal((svg.match(/<line /g) ?? []).length, 2);
  assert.equal((svg.match(/<text /g) ?? []).length, 3);
  assert.match(
    svg,
    /^<svg xmlns="http:\/\/www.w3.org\/2000\/svg" width="180" height="160"/,
  );
});

test("a note name with markup characters cannot break the picture", () => {
  const svg = graphSvg([`a<b>&"c"`], [0, 0], [], colours);
  assert.match(svg, /a&lt;b&gt;&amp;&quot;c&quot;/);
  assert.doesNotMatch(svg, /<b>/);
});

test("a link to a note that is not in the list is left out, and no notes still gives a picture", () => {
  assert.equal(
    (graphSvg(["A"], [0, 0], [0, 5], colours).match(/<line /g) ?? []).length,
    0,
  );
  assert.match(graphSvg([], [], [], colours), /<svg /);
});

test("saved views get the next free name and the oldest goes when the list is full", () => {
  let views = [];
  for (let i = 0; i < MAX_VIEWS + 2; i++)
    views = addView(views, { x: i, y: 0, zoom: 1 });
  assert.equal(views.length, MAX_VIEWS);
  assert.equal(views.at(-1).x, MAX_VIEWS + 1);
  assert.equal(new Set(views.map((v) => v.name)).size, MAX_VIEWS);
});

test("stored views that are damaged are dropped, not trusted", () => {
  assert.deepEqual(parseViews("not json"), []);
  assert.deepEqual(parseViews('{"a":1}'), []);
  assert.deepEqual(
    parseViews(
      '[{"name":"View 1","x":1,"y":2,"zoom":1.5},{"name":"bad","x":"1","y":2,"zoom":1},{"name":"z","x":1,"y":2,"zoom":0}]',
    ),
    [{ name: "View 1", x: 1, y: 2, zoom: 1.5 }],
  );
});
