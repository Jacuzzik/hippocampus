import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("the graph controls have their own strip: no note name is drawn under them", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const tools = page.locator(".brain .tools");
  const labels = page.locator(".brain .labels");
  const canvas = page.locator(".brain canvas.canvas");
  await expect(tools).toBeVisible();
  const toolsBox = await tools.boundingBox();
  const labelsBox = await labels.boundingBox();
  const canvasBox = await canvas.boundingBox();
  if (!toolsBox || !labelsBox || !canvasBox)
    throw new Error("the graph is not on screen");
  expect(labelsBox.y).toBeGreaterThanOrEqual(toolsBox.y + toolsBox.height);
  // The names are placed from the drawing's own corner, so the two layers must start together.
  expect(labelsBox.y).toBe(canvasBox.y);
  expect(labelsBox.height).toBe(canvasBox.height);
});

test("a note in the list shows its full title on hover, and the pane has no stray caption", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const first = page
    .getByRole("list", { name: "Note list" })
    .getByRole("button")
    .first();
  const text = (await first.innerText()).trim();
  await expect(first).toHaveAttribute("title", text);
  await expect(
    page.getByRole("main", { name: "Brain graph" }),
  ).not.toContainText("GRAPH");
});

test("the system numbers keep one width each, so the row does not shift", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const stats = page.getByLabel("System load");
  await expect(stats).toContainText("FREE");
  await expect(stats).not.toContainText("DISK FREE");
  const widths = await stats
    .locator("b")
    .evaluateAll((all) => all.map((b) => getComputedStyle(b).minWidth));
  expect(widths.every((w) => parseFloat(w) > 0)).toBe(true);
});
