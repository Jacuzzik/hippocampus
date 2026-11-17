// Checks the website before launch (15.11): Lighthouse 90+ in every category on every page, and a
// keyboard pass (every link and button can be reached with Tab and shows where focus is).
// Run from app/: node scripts/check-website.mjs   (needs network once, to fetch Lighthouse with npx)
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { readFileSync, readdirSync, mkdtempSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { extname, join } from "node:path";
import { chromium } from "@playwright/test";

const SITE = new URL("../../website/", import.meta.url).pathname;
const LIGHTHOUSE = "lighthouse@12.8.2";
const MIN = 90;
const TYPES = { ".html": "text/html", ".css": "text/css" };

const server = createServer((req, res) => {
  const name =
    (req.url ?? "/").split("?")[0].replace(/^\/+/, "") || "index.html";
  if (name.includes("..") || !TYPES[extname(name)])
    return res.writeHead(404).end();
  try {
    const body = readFileSync(join(SITE, name));
    res.writeHead(200, { "Content-Type": TYPES[extname(name)] }).end(body);
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const base = `http://127.0.0.1:${server.address().port}/`;
const pages = readdirSync(SITE)
  .filter((f) => f.endsWith(".html"))
  .sort();
const out = mkdtempSync(join(tmpdir(), "lighthouse-"));
const failures = [];

for (const page of pages) {
  const report = join(out, `${page}.json`);
  // async, so this script's own web server can answer Lighthouse meanwhile
  await promisify(execFile)(
    "npx",
    [
      "-y",
      LIGHTHOUSE,
      base + page,
      "--quiet",
      "--output=json",
      `--output-path=${report}`,
      "--only-categories=performance,accessibility,best-practices,seo",
      "--chrome-flags=--headless=new --no-sandbox",
    ],
    { env: { ...process.env, CHROME_PATH: chromium.executablePath() } },
  );
  const scores = Object.fromEntries(
    Object.entries(JSON.parse(readFileSync(report, "utf8")).categories).map(
      ([k, v]) => [k, Math.round(v.score * 100)],
    ),
  );
  console.log(page.padEnd(16), JSON.stringify(scores));
  for (const [k, v] of Object.entries(scores))
    if (v < MIN) failures.push(`${page}: ${k} ${v}`);
}

const browser = await chromium.launch();
const tab = await browser.newPage();
for (const page of pages) {
  await tab.goto(base + page);
  const want = await tab.locator("a[href], button").count();
  const seen = new Set();
  for (let i = 0; i < want + 2; i++) {
    await tab.keyboard.press("Tab");
    const focus = await tab.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const s = getComputedStyle(el);
      const ring = s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0;
      return {
        key: el.outerHTML.slice(0, 80),
        ring: ring || s.boxShadow !== "none",
      };
    });
    if (!focus) continue;
    if (!focus.ring) failures.push(`${page}: no visible focus on ${focus.key}`);
    seen.add(focus.key);
  }
  if (seen.size < want)
    failures.push(`${page}: Tab reached ${seen.size} of ${want} controls`);
  const h1 = await tab.locator("h1").count();
  if (h1 !== 1) failures.push(`${page}: ${h1} main headings, want 1`);
}
await browser.close();
server.close();

if (failures.length) {
  console.error("FAILED\n" + failures.join("\n"));
  process.exit(1);
}
console.log(
  `All ${pages.length} pages: Lighthouse ${MIN}+ everywhere, keyboard pass clean.`,
);
