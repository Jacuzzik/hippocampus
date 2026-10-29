// Tests for ui/overlays/allowlist.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import { allowlistAfter } from "../ui/overlays/allowlist.ts";

const tools = [
  { name: "read_note", tier: "read", allowed: true },
  { name: "search_notes", tier: "read", allowed: false },
  { name: "create_note", tier: "write", allowed: true },
];

test("ticking a tool adds it to the allowlist", () => {
  assert.deepEqual(allowlistAfter(tools, "search_notes", true), [
    "read_note",
    "search_notes",
    "create_note",
  ]);
});

test("unticking a tool removes only that tool", () => {
  assert.deepEqual(allowlistAfter(tools, "read_note", false), ["create_note"]);
});
