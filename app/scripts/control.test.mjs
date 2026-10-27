// Tests for ui/control/model.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  activityText,
  filterActivity,
  isSkillName,
  keyStatus,
  overrunOf,
  parseCap,
  usageLine,
} from "../ui/control/model.ts";

test("a cap is reached only when it is set and the usage meets it", () => {
  const caps = { daily: 100, weekly: 0, monthly: 0 };
  assert.equal(
    overrunOf("app", caps, { daily: 99, weekly: 500, monthly: 900 }),
    null,
  );
  assert.deepEqual(
    overrunOf("app", caps, { daily: 100, weekly: 0, monthly: 0 }),
    {
      scope: "app",
      window: "daily",
      used: 100,
      cap: 100,
    },
  );
});

test("usage reads as a fraction, or as no cap when the cap is 0", () => {
  assert.equal(usageLine(1250, 5000), "1,250 of 5,000 tokens");
  assert.equal(usageLine(42, 0), "42 tokens, no cap");
});

test("cap input accepts whole numbers, empty as no cap, and refuses the rest", () => {
  assert.equal(parseCap(" 250 "), 250);
  assert.equal(parseCap(""), 0);
  assert.equal(parseCap("-3"), null);
  assert.equal(parseCap("1.5"), null);
});

test("activity filters keep one kind, and approvals say who decided", () => {
  const rows = [
    {
      ts: "t1",
      kind: "approval",
      tool: "create_note",
      tier: "write",
      approved: true,
    },
    { ts: "t2", kind: "tool", tool: "read_note", tier: "read", status: "done" },
    { ts: "t3", kind: "error", method: "chat", text: "network is Off" },
  ];
  assert.equal(filterActivity(rows, "all").length, 3);
  assert.deepEqual(
    filterActivity(rows, "approval").map((r) => r.tool),
    ["create_note"],
  );
  assert.equal(
    activityText(rows[0]),
    "create_note (write) approved by you on the approval card",
  );
  assert.equal(activityText(rows[2]), "network is Off");
});

test("skill names and key hints are safe to show", () => {
  assert.equal(isSkillName("tidy-notes"), true);
  assert.equal(isSkillName("../tidy"), false);
  assert.equal(isSkillName("Tidy"), false);
  assert.equal(keyStatus(true, "a1b2"), "Saved, ends in …a1b2");
  assert.equal(keyStatus(false, null), "Not set");
});
