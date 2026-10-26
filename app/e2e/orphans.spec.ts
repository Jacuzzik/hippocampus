import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("Hide orphans takes the notes with no links off the graph", async ({
  page,
}) => {
  await mockSidecar(page, { orphan: true });
  await page.goto("/");
  const layer = page.locator(".labels");
  await expect(layer).toHaveAttribute("data-labels", "4");
  await page.getByLabel("Hide orphans").check();
  await expect(layer).toHaveAttribute("data-labels", "3");
  await expect(layer.getByText("Delta")).toHaveCount(0);
});
