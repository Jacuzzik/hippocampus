import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the brain graph loads and the main agent starts idle", async ({
  page,
}) => {
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  await expect(
    page.getByLabel("Agents").getByText("Idle").first(),
  ).toBeVisible();
  await expect(page.getByText("Could not load the vault")).toHaveCount(0);
});

test("a note in the list opens in the graph drawer", async ({ page }) => {
  await page
    .getByRole("list", { name: "Note list" })
    .getByRole("button", { name: "Beta" })
    .click();
  await expect(
    page.getByRole("complementary", { name: "Note details" }),
  ).toContainText("beta.md");
});

for (const [width, height] of [
  [960, 600],
  [1280, 800],
] as const) {
  test(`with the note drawer open, all 3 notes stay in the canvas at ${width} by ${height}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height });
    const canvas = page.locator("canvas.canvas");
    const before = (await canvas.boundingBox())?.width ?? 0;
    await page
      .getByRole("list", { name: "Note list" })
      .getByRole("button", { name: "Beta" })
      .click();
    const drawer = page.getByRole("complementary", { name: "Note details" });
    await expect(drawer).toBeVisible();
    // The drawer narrows the canvas; wait for that resize and the frame that refits the graph.
    await expect
      .poll(async () => (await canvas.boundingBox())?.width ?? 0)
      .toBeLessThan(before);
    await page.evaluate(
      () =>
        new Promise((done) =>
          requestAnimationFrame(() => requestAnimationFrame(done)),
        ),
    );
    await expect(canvas).toHaveAttribute("data-in-view", "3");
    const [c, d] = [await canvas.boundingBox(), await drawer.boundingBox()];
    expect(c && d && c.x + c.width <= d.x).toBe(true);
  });
}

test("the ribbon hides and shows the note list", async ({ page }) => {
  const toggle = page.getByRole("button", { name: "Note list" });
  await toggle.click();
  await expect(page.getByRole("complementary", { name: "Notes" })).toHaveCount(
    0,
  );
  await toggle.click();
  await expect(
    page.getByRole("complementary", { name: "Notes" }),
  ).toBeVisible();
});

test("the layout fits a 960 by 600 window without scrolling", async ({
  page,
}) => {
  await page.setViewportSize({ width: 960, height: 600 });
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  const fits = await page.evaluate(
    () =>
      document.documentElement.scrollWidth <=
        document.documentElement.clientWidth &&
      document.documentElement.scrollHeight <=
        document.documentElement.clientHeight,
  );
  expect(fits).toBe(true);
});

test("the graph labels its notes in the default arc layout", async ({
  page,
}) => {
  // The arc layout is still on purpose, so its labels stay where they are placed.
  const layer = page.locator(".labels");
  const shown = layer.locator(".label");
  await expect(layer).not.toHaveAttribute("data-labels", "0");
  await expect(shown.first()).toBeVisible();
  await expect(shown.first()).toHaveAttribute("style", /transform/);
});

test("Fit graph brings every note back into the canvas after a zoom", async ({
  page,
}) => {
  const canvas = page.locator("canvas.canvas");
  await expect(canvas).toHaveAttribute("data-in-view", "3");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("the graph canvas has no box");
  // Pan the graph far to the right, so no note is in view.
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 2000, box.y + box.height / 2, {
    steps: 10,
  });
  await page.mouse.up();
  await expect
    .poll(async () => canvas.getAttribute("data-in-view"))
    .not.toBe("3");
  await page.getByRole("button", { name: "Fit graph" }).click();
  await expect(canvas).toHaveAttribute("data-in-view", "3");
});

test("a tag in the tags pane filters the note list", async ({ page }) => {
  await page
    .getByRole("list", { name: "Tags" })
    .getByRole("button", { name: /#idea/ })
    .click();
  await expect(page.getByText("2 of 3")).toBeVisible();
  await expect(
    page
      .getByRole("list", { name: "Note list" })
      .getByRole("button", { name: "Beta" }),
  ).toHaveCount(0);
});
