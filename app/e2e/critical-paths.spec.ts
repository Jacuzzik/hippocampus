import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the brain graph loads and the orb starts idle", async ({ page }) => {
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  await expect(
    page.getByRole("status", { name: "Assistant: Idle" }).first(),
  ).toBeVisible();
  await expect(page.getByText("Could not load the vault")).toHaveCount(0);
});

test("a question is answered and the tool log shows the read", async ({
  page,
}) => {
  await page
    .getByLabel("Message the assistant")
    .fill("search my notes for alpha");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.getByText("Found Alpha in projects/alpha.md."),
  ).toBeVisible();
  const log = page.getByRole("region", { name: "Tool log" });
  await expect(log.getByText("search_notes")).toBeVisible();
  await expect(log.getByText("done")).toBeVisible();
});

test("a write waits for approval, shows the exact change, then runs", async ({
  page,
}) => {
  await page.getByLabel("Message the assistant").fill("make a new idea note");
  await page.getByRole("button", { name: "Send" }).click();
  const card = page.getByRole("group", { name: "Approval needed" });
  await expect(card).toContainText("+# New idea");
  await expect(
    page.getByRole("status", { name: "Assistant: Waiting for you" }).first(),
  ).toBeVisible();
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Created ideas/new.md.")).toBeVisible();
  await expect(card).toHaveCount(0);
});

test("declining a write leaves the note uncreated", async ({ page }) => {
  await page.getByLabel("Message the assistant").fill("make a new idea note");
  await page.getByRole("button", { name: "Send" }).click();
  await page
    .getByRole("group", { name: "Approval needed" })
    .getByRole("button", { name: "Decline" })
    .click();
  await expect(page.getByText("Okay, I did not create it.")).toBeVisible();
});

test("Stop ends a running chat at once", async ({ page }) => {
  await page.getByLabel("Message the assistant").fill("a long task");
  await page.getByRole("button", { name: "Send" }).click();
  const stop = page.getByRole("button", { name: "Stop" });
  await expect(stop).toBeEnabled();
  const started = Date.now();
  await stop.click();
  await expect(page.getByText("Stopped.")).toBeVisible();
  expect(Date.now() - started).toBeLessThan(1000);
  await expect(
    page.getByRole("status", { name: "Assistant: Idle" }).first(),
  ).toBeVisible();
});

test("Escape is the keyboard stop", async ({ page }) => {
  await page.getByLabel("Message the assistant").fill("a long task");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: "Stop" })).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(page.getByText("Stopped.")).toBeVisible();
});

test("reduced motion turns off the orb pulse", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByLabel("Message the assistant").fill("a long task");
  await page.getByRole("button", { name: "Send" }).click();
  const orb = page.locator(".orb[data-state='thinking']").first();
  await expect(orb).toBeVisible();
  await expect(orb).toHaveCSS("animation-name", "none");
  await page.getByRole("button", { name: "Stop" }).click();
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
    const canvas = page.locator("canvas");
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

test("the graph labels its notes and the nodes drift between frames", async ({
  page,
}) => {
  const layer = page.locator(".labels");
  const shown = layer.locator(".label");
  await expect(layer).not.toHaveAttribute("data-labels", "0");
  await expect(shown.first()).toBeVisible();
  const before = await shown.first().evaluate((el) => el.style.transform);
  // The drift is slow; poll until the first label has moved.
  await expect
    .poll(() => shown.first().evaluate((el) => el.style.transform))
    .not.toBe(before);
});

test("Fit graph brings every note back into the canvas after a zoom", async ({
  page,
}) => {
  const canvas = page.locator("canvas");
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
