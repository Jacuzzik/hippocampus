// Run with `node --test scripts/check-tokens.mjs`. Enforces the design-token
// rule: colors come from design/tokens.json, never hardcoded in the UI.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { buildVariables, loadTokens } from "./build-tokens.mjs";

const UI_DIR = fileURLToPath(new URL("../ui/", import.meta.url));
const TAURI_CONF = fileURLToPath(
  new URL("../src-tauri/tauri.conf.json", import.meta.url),
);
const RAW_COLOR = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?)\(/i;

test("every token reference resolves", () => {
  const vars = buildVariables(loadTokens());
  assert.ok(vars.length > 0);
  for (const [name, value] of vars) {
    assert.doesNotMatch(value, /\{/, `${name} has an unresolved reference`);
  }
});

test("UI source has no hardcoded colors", () => {
  const offenders = readdirSync(UI_DIR, { recursive: true })
    .filter(
      (file) => /\.(svelte|css|ts)$/.test(file) && !file.endsWith("tokens.css"),
    )
    .flatMap((file) =>
      readFileSync(join(UI_DIR, file), "utf8")
        .split("\n")
        .map((line, i) => ({ file, line: i + 1, text: line }))
        .filter(({ text }) => RAW_COLOR.test(text)),
    );
  assert.deepEqual(
    offenders,
    [],
    "Use var(--color-*) instead of raw color values",
  );
});

test("Tauri window minimum size matches layout tokens", () => {
  const { layout } = loadTokens();
  const [window] = JSON.parse(readFileSync(TAURI_CONF, "utf8")).app.windows;
  assert.equal(`${window.minWidth}px`, layout["window-min-width"].$value);
  assert.equal(`${window.minHeight}px`, layout["window-min-height"].$value);
});
