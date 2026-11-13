// Tests for ui/spend.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import { formatTokens, meter } from "../ui/spend.ts";

test("token counts are short and readable", () => {
  assert.equal(formatTokens(0), "0");
  assert.equal(formatTokens(950), "950");
  assert.equal(formatTokens(12340), "12.3k");
  assert.equal(formatTokens(50000), "50k");
  assert.equal(formatTokens(2_500_000), "2.5M");
});

test("with no cap the meter shows only what was used", () => {
  assert.deepEqual(meter(1200, 0), { text: "1.2k today", level: "ok" });
});

test("the meter warns at 80 percent of the cap and again at the cap", () => {
  assert.equal(meter(39_999, 50_000).level, "ok");
  assert.equal(meter(40_000, 50_000).level, "near");
  assert.equal(meter(50_000, 50_000).level, "over");
  assert.equal(meter(51_000, 50_000).text, "51k of 50k today");
});
