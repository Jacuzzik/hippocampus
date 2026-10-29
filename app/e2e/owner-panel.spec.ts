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

test("the inbox tab lists agent messages", async ({ page }) => {
  await page.getByRole("tab", { name: "inbox" }).click();
  await expect(page.getByRole("region", { name: "Inbox" })).toContainText("Research the plan");
});

test("the settings button opens the saved settings read only", async ({ page }) => {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("button", { name: "Agents and models" }).click();
  await expect(dialog).toContainText("claude-sonnet-5-5");
});

test("the settings options show one section at a time", async ({ page }) => {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("button", { name: "Agents and models" }).click();
  await expect(dialog).toContainText("Ollama model");
  await expect(dialog).not.toContainText("Assistant, daily");
});

test("the memory tab lists each agent's notes", async ({ page }) => {
  await page.getByRole("tab", { name: "memory" }).click();
  await expect(page.getByRole("region", { name: "Memory" })).toContainText("kevin");
});
