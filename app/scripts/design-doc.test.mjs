import assert from "node:assert/strict";
import { test } from "node:test";
import { buildDesignDoc, readDesignDoc } from "./build-design-doc.mjs";
import { loadTokens } from "./build-tokens.mjs";

test("design/DESIGN.md is the one generated from the tokens", () => {
  assert.equal(
    readDesignDoc(),
    buildDesignDoc(loadTokens()),
    "design/DESIGN.md is out of date: run `npm run tokens` in app/",
  );
});

test("the page names a colour, a spacing step and a duration", () => {
  const doc = buildDesignDoc(loadTokens());
  assert.match(doc, /--color-bg-0/);
  assert.match(doc, /--space-2/);
  assert.match(doc, /--duration-base/);
});
