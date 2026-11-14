import assert from "node:assert/strict";
import { test } from "node:test";
import { buildCallsDoc, listCalls, readCallsDoc } from "./build-calls-doc.mjs";

test("docs/BACKEND-CALLS.md lists every backend call the window makes", () => {
  assert.equal(
    readCallsDoc(),
    buildCallsDoc(),
    "docs/BACKEND-CALLS.md is out of date: run `node scripts/build-calls-doc.mjs` in app/",
  );
});

test("the files that call the backend without a waiting state do not grow in number", () => {
  const without = listCalls().filter((row) => !row.waits);
  // Lower this number when a file gains a waiting state; never raise it.
  assert.ok(
    without.length <= LIMIT,
    `${without.length} files call the backend with no waiting state: ${without.map((row) => row.file).join(", ")}`,
  );
});

const LIMIT = 15;
