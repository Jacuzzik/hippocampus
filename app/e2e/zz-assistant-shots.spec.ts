import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

const SHOTS = "/tmp/claude-1000/-home-thalha-Documents-Obsidian-Munder-Difflin-worktrees-worker-assistant-files-voice/a3481773-169d-4205-b563-da95244b79d5/scratchpad/shots";
const INPUT = "/tmp/claude-1000/-home-thalha-Documents-Obsidian-Munder-Difflin-worktrees-worker-assistant-files-voice/a3481773-169d-4205-b563-da95244b79d5/scratchpad/input";

test("assistant files and voice shots", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("http://127.0.0.1:1431/");
  const panel = page.locator("aside.assistant");
  await expect(panel.getByRole("button", { name: "+ files" })).toBeEnabled();
  await expect(panel.getByRole("button", { name: "voice" })).toBeEnabled();
  await panel.screenshot({ path: SHOTS + "/assistant-files-default.png" });

  await panel.locator('input[type="file"]').setInputFiles([INPUT + "/plan.md", INPUT + "/data.csv"]);
  await expect(panel.getByLabel("Attached files").getByText("plan.md")).toBeVisible();
  await panel.screenshot({ path: SHOTS + "/assistant-files-chips.png" });

  await panel.getByRole("button", { name: "Remove data.csv" }).click();
  await expect(panel.getByText("data.csv")).toHaveCount(0);
  await panel.getByRole("button", { name: "Remove plan.md" }).click();
  await expect(panel.getByLabel("Attached files")).toHaveCount(0);

  await panel.locator('input[type="file"]').setInputFiles([INPUT + "/plan.md"]);
  await panel.getByPlaceholder("Ask about your notes").fill("Summarize it");
  await panel.getByRole("button", { name: "Send" }).click();
  await expect(panel.locator(".message.user").first()).toContainText("Attached file: plan.md");
  await expect(panel.locator(".message.user").first()).toContainText("Summarize it");

  await panel.getByRole("button", { name: "voice" }).click();
  await expect(panel.getByRole("status")).toContainText("No speech-to-text source");
  await panel.screenshot({ path: SHOTS + "/assistant-voice-no-source.png" });
});
