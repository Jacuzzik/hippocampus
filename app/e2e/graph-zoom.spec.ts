import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// 12.11: the wheel zoom glides over a few frames; reduced motion zooms at once.
async function zoomAfterWheel(page: import("@playwright/test").Page) {
  await mockSidecar(page);
  await page.goto("/");
  const canvas = page
    .getByRole("main", { name: "Brain graph" })
    .locator("canvas.canvas");
  await expect(canvas).toHaveAttribute("data-in-view", "3");
  const before = Number(await canvas.getAttribute("data-zoom"));
  const box = await canvas.boundingBox();
  if (!box) throw new Error("no canvas box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -400);
  return { canvas, before };
}

test("a wheel zoom glides to its target", async ({ page }) => {
  const { canvas, before } = await zoomAfterWheel(page);
  const target = before * Math.exp(400 * 0.0015);
  const seen = new Set<string>();
  await expect
    .poll(async () => {
      const z = (await canvas.getAttribute("data-zoom")) ?? "";
      seen.add(z);
      return Math.abs(Number(z) - target) < 0.01;
    })
    .toBe(true);
  // More than the start and the end were drawn on the way.
  expect(seen.size).toBeGreaterThan(1);
});

test("with reduced motion the wheel zooms at once", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const { canvas, before } = await zoomAfterWheel(page);
  const target = before * Math.exp(400 * 0.0015);
  await expect
    .poll(async () => Number(await canvas.getAttribute("data-zoom")))
    .toBeCloseTo(target, 2);
});
