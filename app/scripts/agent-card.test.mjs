// Tests for ui/assistant/agentCard.ts: faces exist, the face pick is stable, and each accent's text passes AA.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { ACCENTS, FACES, faceFor } from "../ui/assistant/agentCard.ts";

const tokens = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../design/tokens.json", import.meta.url)),
    "utf8",
  ),
);

function resolve(value) {
  const ref = /^\{color\.(primitive|semantic)\.(.+)\}$/.exec(value);
  return ref ? resolve(tokens.color[ref[1]][ref[2]].$value) : value;
}

function luminance(hex) {
  const n = Number.parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

test("every face in the card set is a file on disk", () => {
  for (const file of FACES) {
    assert.ok(
      existsSync(new URL(`../ui/assets/faces-new/${file}`, import.meta.url)),
      file,
    );
  }
});

test("the same agent name always gets the same face from the set", () => {
  assert.ok(FACES.includes(faceFor("Assistant")));
  assert.equal(faceFor("Assistant"), faceFor("Assistant"));
});

test("each accent is a colour token, and its text passes AA normal text (4.5:1)", () => {
  for (const [accent, { text }] of Object.entries(ACCENTS)) {
    const background = resolve(tokens.color.semantic[accent].$value);
    const foreground = resolve(tokens.color.semantic[text].$value);
    assert.ok(ratio(background, foreground) >= 4.5, `${accent} on ${text}`);
  }
});
