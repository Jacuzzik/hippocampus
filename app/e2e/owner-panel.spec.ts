import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the bottom agent bar shows HIPPO with its provider", async ({ page }) => {
  const bar = page.getByLabel("Agents");
  await expect(bar.getByText("HIPPO")).toBeVisible();
  await expect(bar.getByText(/Claude Code|Ollama/)).toBeVisible();
});

test("the bottom agent bar shows a token placeholder until usage is counted", async ({ page }) => {
  await expect(page.getByLabel("Agents").getByText("— tokens").first()).toBeVisible();
});

test("+ Add agent opens the add-agent steps in the Control panel", async ({
  page,
}) => {
  await page.getByLabel("Agents").getByRole("button", { name: "+ Add agent" }).click();
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(dialog.locator("#control-add-agent")).toBeVisible();
});

test("the tasks tab opens the task board", async ({ page }) => {
  await page.getByRole("tab", { name: "tasks" }).click();
  await expect(page.getByRole("region", { name: "Tasks" })).toBeVisible();
});
