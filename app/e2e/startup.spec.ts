import { writeFileSync, readFileSync, existsSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// B.06: how long the window takes from navigation until its start-up work has settled (with the bridge mocked,
// so this is the window's own cost, not the backend's). The budget is loose so a busy computer does not fail it.
const READY_BUDGET_MS = 8000;

test("the window finishes its start-up work within the budget", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.waitForFunction(
    () => performance.getEntriesByName("hippo-ready").length > 0,
  );
  const ready = await page.evaluate(() =>
    Math.round(performance.getEntriesByName("hippo-ready")[0].startTime),
  );
  expect(ready).toBeGreaterThan(0);
  expect(ready).toBeLessThan(READY_BUDGET_MS);
  // `HIPPO_PERF_FILE=docs/perf/<version>.json npx playwright test e2e/startup.spec.ts` records the number.
  const file = process.env.HIPPO_PERF_FILE;
  if (file && existsSync(file)) {
    const saved = JSON.parse(readFileSync(file, "utf8"));
    saved.window_ready_ms = ready;
    writeFileSync(file, JSON.stringify(saved, null, 2) + "\n");
  }
});
