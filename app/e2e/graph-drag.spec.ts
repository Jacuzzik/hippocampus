import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// Labels sit 8px right of and 7px above the node's screen point (see BrainGraph.svelte drawLabels).
const LABEL_DX = 8;
const LABEL_DY = 7;

// Dragging a node pulls the notes linked to it, and the graph comes to rest after the drop.
test("dragging a node pulls its linked node along and lets it settle", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const graph = page.getByRole("main", { name: "Brain graph" });
  const canvas = graph.locator("canvas.canvas");
  await expect(canvas).toHaveAttribute("data-in-view", "3");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("the graph canvas has no box");

  // Alpha links to Beta; Gamma links only to Beta, so it is two hops from Alpha.
  const at = async (title: string) => {
    const style = await graph
      .locator(".label", { hasText: new RegExp(`^${title}$`) })
      .getAttribute("style");
    const m = /translate\((-?[\d.]+)px, (-?[\d.]+)px\)/.exec(style ?? "");
    if (!m) throw new Error(`no label for ${title}`);
    return { x: box.x + Number(m[1]), y: box.y + Number(m[2]) };
  };
  const moved = (a: { x: number; y: number }, b: { x: number; y: number }) =>
    Math.hypot(a.x - b.x, a.y - b.y);

  const alpha0 = await at("Alpha");
  const beta0 = await at("Beta");

  await page.mouse.move(alpha0.x - LABEL_DX, alpha0.y + LABEL_DY);
  await page.mouse.down();
  await page.mouse.move(alpha0.x - LABEL_DX + 60, alpha0.y + LABEL_DY, {
    steps: 12,
  });

  // While held, Alpha stays under the pointer and Beta, linked to it, follows.
  // The layout is a plain force layout (as in Obsidian), so notes further along the chain may move too.
  await expect
    .poll(async () => moved(await at("Beta"), beta0), { timeout: 2000 })
    .toBeGreaterThan(20); // Alpha moved 60px; Beta follows by about half of that
  const held = moved(await at("Alpha"), alpha0);
  expect(held).toBeGreaterThan(55);
  expect(held).toBeLessThan(65);

  await page.mouse.up();
  // Released: the graph comes to rest instead of drifting on.
  await expect
    .poll(
      async () => {
        const first = await at("Beta");
        await page.waitForTimeout(400);
        return moved(await at("Beta"), first);
      },
      { timeout: 8000 },
    )
    .toBeLessThan(1);
});
