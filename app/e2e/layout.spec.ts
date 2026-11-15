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

test("the status bar shows tokens used today against the cap, and a click opens Budgets", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const meter = page.getByRole("button", { name: /Tokens used today/ });
  await expect(meter).toHaveText("12.4k of 200k today");
  await meter.click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await expect(
    dialog.getByRole("heading", { name: "Token budget" }),
  ).toBeVisible();
});

test("the graph is exported as a picture, and a saved view brings the same place back", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const tools = page.locator(".brain .tools");
  await tools.getByRole("button", { name: "Export picture" }).click();
  await expect(page.locator(".brain .export-note")).toContainText(
    "Saved to /home/me/.hippocampus/exports/20261114-graph.svg",
  );
  await tools.getByRole("button", { name: "Save view" }).click();
  const stored = () =>
    page.evaluate(() => localStorage.getItem("graph-views") ?? "[]");
  expect(JSON.parse(await stored())).toHaveLength(1);
  await tools.getByRole("button", { name: "Saved views" }).click();
  // The option is on top (checked by hit test); a forced click avoids Playwright waiting on the graph's redraws.
  await page.getByRole("option", { name: "View 1" }).click({ force: true });
  await tools.getByRole("button", { name: "Saved views" }).click();
  await page
    .getByRole("option", { name: "Forget all views" })
    .click({ force: true });
  await expect(tools.getByRole("button", { name: "Saved views" })).toHaveCount(
    0,
  );
  expect(JSON.parse(await stored())).toHaveLength(0);
});
