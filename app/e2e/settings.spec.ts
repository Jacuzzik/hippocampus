import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("settings has six tabs and each one opens", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Control panel" }).click();
  await page
    .getByRole("dialog", { name: "Control panel" })
    .getByRole("button", { name: "Open settings" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  const tabs = dialog.getByRole("tab");
  await expect(tabs).toHaveText([
    "General",
    "Prerequisites",
    "Autonomy and budgets",
    "Integrations",
    "Dictation and meeting",
    "Memory and knowledge",
  ]);
  await dialog.getByRole("tab", { name: "Prerequisites" }).click();
  await expect(dialog.getByText("Running")).toBeVisible();
  await dialog.getByRole("tab", { name: "Dictation and meeting" }).click();
  await expect(
    dialog.getByText("Not set up: dictation and meeting capture"),
  ).toBeVisible();
});
