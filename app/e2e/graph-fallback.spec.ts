import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// Simulates a browser with no WebGL 2 (some phone browsers): the graph must still draw.
test("the brain graph draws on a 2D canvas when WebGL 2 is missing", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      type: string,
      ...rest: unknown[]
    ) {
      if (type === "webgl2") return null;
      return (original as (...a: unknown[]) => unknown).call(
        this,
        type,
        ...rest,
      );
    } as typeof original;
  });
  await mockSidecar(page);
  await page.goto("/");
  const canvas = page
    .getByRole("main", { name: "Brain graph" })
    .locator("canvas");
  await expect(canvas).toHaveAttribute("data-in-view", "3");
  await expect(page.getByText("The graph cannot be drawn")).toHaveCount(0);
  // Nodes and edges are painted: more than the background colour is on the canvas.
  const colours = await canvas.evaluate((c: HTMLCanvasElement) => {
    const ctx = c.getContext("2d");
    if (!ctx) throw new Error("the graph canvas has no 2D context");
    const { data } = ctx.getImageData(0, 0, c.width, c.height);
    const seen = new Set<number>();
    for (let i = 0; i < data.length; i += 4 * 97)
      seen.add(
        (data[i] ?? 0) * 65536 + (data[i + 1] ?? 0) * 256 + (data[i + 2] ?? 0),
      );
    return seen.size;
  });
  expect(colours).toBeGreaterThan(2);
});
