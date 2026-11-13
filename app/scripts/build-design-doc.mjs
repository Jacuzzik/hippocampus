// Generates design/DESIGN.md from design/tokens.json: every token with its value, so the page cannot drift.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { loadTokens, resolveValue } from "./build-tokens.mjs";

export const DOC_PATH = fileURLToPath(
  new URL("../../design/DESIGN.md", import.meta.url),
);

function rows(tokens, group, prefix) {
  return Object.entries(group)
    .filter(([name]) => !name.startsWith("$"))
    .map(
      ([name, token]) =>
        `| \`--${prefix}-${name}\` | \`${resolveValue(tokens, token.$value)}\` |`,
    );
}

function table(title, lines, note = "") {
  return `## ${title}\n\n${note ? `${note}\n\n` : ""}| Variable | Value |\n|---|---|\n${lines.join("\n")}\n`;
}

export function buildDesignDoc(tokens) {
  const light = tokens.color.light ?? {};
  const lightRows = rows(tokens, light, "color");
  const fontRows = Object.entries(tokens.font).map(
    ([name, text]) => `| \`--font-${name}\` | ${text} |`,
  );
  const parts = [
    "# Design tokens\n",
    "Generated from `design/tokens.json` by `app/scripts/build-design-doc.mjs`. Do not edit by hand: run `npm run tokens` in `app/`.",
    "Components use these variables and nothing else: `npm test` fails on a raw colour or font in a component.\n",
    table(
      "Colour (dark, the default)",
      rows(tokens, tokens.color.semantic, "color"),
    ),
    table("Colour (light theme, only what differs)", lightRows),
    table("Spacing", rows(tokens, tokens.space, "space")),
    table("Radius", rows(tokens, tokens.radius, "radius")),
    table("Text size", rows(tokens, tokens["font-size"], "font-size")),
    table("Fonts", fontRows),
    table("Layout", rows(tokens, tokens.layout, "layout")),
    table("Motion: durations", rows(tokens, tokens.duration, "duration")),
    table("Motion: easing", rows(tokens, tokens.ease, "ease")),
  ];
  return `${parts.join("\n")}\n`;
}

export function readDesignDoc(path = DOC_PATH) {
  return readFileSync(path, "utf8");
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  writeFileSync(DOC_PATH, buildDesignDoc(loadTokens()));
  console.log(`Wrote ${DOC_PATH}`);
}
