// The language catalogues: same phrases in each, none empty, and every phrase the components ask for exists.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { AR } from "../ui/i18n/catalog.ar.ts";
import { ZH } from "../ui/i18n/catalog.zh.ts";
import { SETTINGS_PAGES } from "../ui/settings/model.ts";

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.(svelte|ts)$/.test(name) ? [path] : [];
  });
}

test("every language has the same phrases, none empty", () => {
  assert.deepEqual(Object.keys(ZH).sort(), Object.keys(AR).sort());
  for (const catalog of [ZH, AR])
    for (const [phrase, text] of Object.entries(catalog)) {
      assert.ok(text.trim(), `${phrase} has no translation`);
      // A hole like {n} in the English must be in the translation, or the number would be lost.
      for (const hole of phrase.match(/\{\w+\}/g) ?? [])
        assert.ok(
          text.includes(hole),
          `${phrase}: the translation drops ${hole}`,
        );
    }
});

test("every phrase a component passes to t() or tf() has a translation", () => {
  const asked = new Set();
  const root = new URL("../ui", import.meta.url).pathname;
  for (const path of files(root)) {
    const text = readFileSync(path, "utf8");
    for (const m of text.matchAll(/\btf?\(\s*"((?:[^"\\]|\\.)+)"/g))
      asked.add(m[1]);
  }
  assert.ok(asked.size > 20, "the components should use t() for the shell");
  const missing = [...asked].filter(
    (phrase) => !(phrase in ZH) || !(phrase in AR),
  );
  assert.deepEqual(missing, []);
});

test("directional UI spacing and alignment use logical CSS properties", () => {
  const root = new URL("../ui", import.meta.url).pathname;
  const physical =
    /\b(?:margin|padding)-(?:left|right)\s*:|(?:^|\s)(?:left|right)\s*:|\btext-align:\s*(?:left|right)\b/m;
  const found = files(root).filter((path) =>
    physical.test(readFileSync(path, "utf8")),
  );
  assert.deepEqual(
    found,
    [],
    "use inline-start/end and text-align start/end so RTL layouts mirror",
  );
});

test("the Settings page names and the tour's own text are translated", () => {
  const tour = readFileSync(
    new URL("../ui/overlays/Tour.svelte", import.meta.url),
    "utf8",
  );
  const phrases = [
    ...SETTINGS_PAGES.map((p) => p.id),
    ...[...tour.matchAll(/(?:title|text):\s*\n?\s*"((?:[^"\\]|\\.)+)"/g)].map(
      (m) => m[1],
    ),
  ];
  assert.ok(phrases.length > 20);
  const missing = phrases.filter(
    (phrase) => !(phrase in ZH) || !(phrase in AR),
  );
  assert.deepEqual(missing, []);
});
