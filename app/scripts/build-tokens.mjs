// Generates ui/styles/tokens.css from design/tokens.json, the single source of
// truth for colors, spacing, and layout. Components use only these variables.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

export const TOKENS_PATH = fileURLToPath(
  new URL("../../design/tokens.json", import.meta.url),
);
export const CSS_PATH = fileURLToPath(
  new URL("../ui/styles/tokens.css", import.meta.url),
);

// Sections emitted as CSS variables, keyed by token path prefix.
const SECTIONS = [
  ["color.semantic", "color"],
  ["space", "space"],
  ["radius", "radius"],
  ["font-size", "font-size"],
  ["layout", "layout"],
];

export function loadTokens(path = TOKENS_PATH) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function lookup(tokens, dottedPath) {
  let node = tokens;
  for (const key of dottedPath.split(".")) {
    if (node === null || typeof node !== "object" || !(key in node)) {
      throw new Error(`Unknown token path: ${dottedPath}`);
    }
    node = node[key];
  }
  return node;
}

// Resolves a token's $value, following {a.b.c} references.
export function resolveValue(tokens, value, seen = new Set()) {
  const ref = /^\{([^}]+)\}$/.exec(value);
  if (!ref) return value;
  const target = ref[1];
  if (seen.has(target)) throw new Error(`Circular token reference: ${target}`);
  seen.add(target);
  const node = lookup(tokens, target);
  if (typeof node?.$value !== "string")
    throw new Error(`Token has no $value: ${target}`);
  return resolveValue(tokens, node.$value, seen);
}

// "Inter (fallback: system-ui, sans-serif)" -> font-family stack that prefers
// the named face (installed locally; no font package is bundled).
export function fontStack(description) {
  const match = /^(.+?)\s*\(fallback:\s*(.+)\)$/.exec(description);
  if (!match) throw new Error(`Unrecognized font token: ${description}`);
  const [, name, fallbacks] = match;
  return [
    `"${name} Variable"`,
    `"${name}"`,
    ...fallbacks.split(",").map((f) => f.trim()),
  ].join(", ");
}

export function buildVariables(tokens) {
  const vars = [];
  for (const [path, prefix] of SECTIONS) {
    for (const [name, token] of Object.entries(lookup(tokens, path))) {
      vars.push([`--${prefix}-${name}`, resolveValue(tokens, token.$value)]);
    }
  }
  for (const [name, description] of Object.entries(tokens.font)) {
    vars.push([`--font-${name}`, fontStack(description)]);
  }
  return vars;
}

// The light theme's colours: only the ones that differ from the dark default.
export function buildLightVariables(tokens) {
  return Object.entries(tokens.color.light ?? {})
    .filter(([name]) => !name.startsWith("$"))
    .map(([name, token]) => {
      if (!(name in tokens.color.semantic))
        throw new Error(`Light colour has no dark default: ${name}`);
      return [`--color-${name}`, resolveValue(tokens, token.$value)];
    });
}

export function buildCss(tokens) {
  const lines = buildVariables(tokens).map(
    ([name, value]) => `  ${name}: ${value};`,
  );
  const light = buildLightVariables(tokens).map(
    ([name, value]) => `  ${name}: ${value};`,
  );
  // color-scheme makes the browser's own parts (scrollbars, pickers, menus) follow the theme.
  return `/* Generated from design/tokens.json by scripts/build-tokens.mjs. Do not edit. */\n:root {\n  color-scheme: dark;\n${lines.join("\n")}\n}\n\n:root[data-theme="light"] {\n  color-scheme: light;\n${light.join("\n")}\n}\n`;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  writeFileSync(CSS_PATH, buildCss(loadTokens()));
  console.log(`Wrote ${CSS_PATH}`);
}
