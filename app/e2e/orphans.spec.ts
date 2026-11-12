import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("Hide orphans takes the notes with no links off the graph", async ({
  page,
}) => {
  await mockSidecar(page, { orphan: true });
  await page.goto("/");
  const layer = page.locator(".labels");
  await expect(layer).toHaveAttribute("data-labels", "4");
  // The checkbox itself is drawn as a switch, so the label is what a person clicks.
  await page.getByText("Hide orphans").click();
  await expect(page.getByLabel("Hide orphans")).toBeChecked();
  await expect(layer).toHaveAttribute("data-labels", "3");
  await expect(layer.getByText("Delta")).toHaveCount(0);
});
