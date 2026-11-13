// WCAG 2.1 AA contrast for the text colours the UI uses, computed from design/tokens.json.
// Normal text needs 4.5:1; non-text UI parts (borders, icons) need 3:1.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const tokens = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../design/tokens.json", import.meta.url)),
    "utf8",
  ),
);
const primitive = Object.fromEntries(
  Object.entries(tokens.color.primitive).map(([k, v]) => [k, v.$value]),
);
const semantic = Object.fromEntries(
  Object.entries(tokens.color.semantic).map(([k, v]) => [k, v.$value]),
);

function hex(value) {
  const ref = /^\{color\.primitive\.(.+)\}$/.exec(value);
  const raw = ref ? primitive[ref[1]] : value;
  const m = /^#([0-9a-f]{6})$/i.exec(raw);
  assert.ok(m, `not a solid hex colour: ${value}`);
  const n = Number.parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function luminance(rgb) {
  const [r, g, b] = rgb.map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT_PAIRS = [
  ["text", "bg-0"],
  ["text", "bg-1"],
  ["text-muted", "bg-0"],
  ["text-muted", "bg-1"],
  ["danger", "bg-1"],
  ["accent-on", "accent"],
];

for (const [fg, bg] of TEXT_PAIRS) {
  test(`${fg} on ${bg} meets 4.5:1 for normal text`, () => {
    const value = ratio(hex(semantic[fg]), hex(semantic[bg]));
    assert.ok(value >= 4.5, `${fg} on ${bg} is ${value.toFixed(2)}:1`);
  });
}

// The orb's "thinking" colour is 2.97:1, below 3:1. The state is also written beside the orb
// ("Thinking"), so colour is not the only cue; keep it out of this list.
test("confirm and danger borders meet 3:1 against the panel", () => {
  for (const name of ["confirm", "danger"]) {
    const value = ratio(hex(semantic[name]), hex(semantic["bg-1"]));
    assert.ok(value >= 3, `${name} on bg-1 is ${value.toFixed(2)}:1`);
  }
});

// The light theme changes only some colours; the rest keep their dark-theme value.
const light = {
  ...semantic,
  ...Object.fromEntries(
    Object.entries(tokens.color.light)
      .filter(([k]) => !k.startsWith("$"))
      .map(([k, v]) => [k, v.$value]),
  ),
};
const LIGHT_TEXT_PAIRS = [
  ...TEXT_PAIRS,
  ["text-subtle", "bg-0"],
  ["text-subtle", "bg-1"],
  ["link", "bg-0"],
  ["confirm", "bg-1"],
  ["success", "bg-1"],
  ["pending", "bg-1"],
  ["md-text", "md-bg-0"],
  ["md-text-muted", "md-bg-0"],
  ["md-danger", "md-bg-0"],
  ["md-accent-on", "md-accent"],
];

for (const [fg, bg] of LIGHT_TEXT_PAIRS) {
  test(`light theme: ${fg} on ${bg} meets 4.5:1 for normal text`, () => {
    const value = ratio(hex(light[fg]), hex(light[bg]));
    assert.ok(value >= 4.5, `${fg} on ${bg} is ${value.toFixed(2)}:1`);
  });
}

test("the light theme only changes colours that exist in the dark theme", () => {
  for (const name of Object.keys(tokens.color.light))
    if (!name.startsWith("$"))
      assert.ok(name in semantic, `${name} has no dark default`);
});
