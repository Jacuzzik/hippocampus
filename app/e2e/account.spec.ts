import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// The brain is made by the app on first start, so Setup no longer asks for a folder or a key.
// The vault folder is changed in Settings > General and keys are saved in Settings > Models and keys.

async function openSettings(page: import("@playwright/test").Page) {
  await page.keyboard.press("Control+p");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await palette.getByRole("combobox").fill("settings");
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await expect(dialog).toBeVisible();
  return dialog;
}

test("the vault folder is changed in Settings, and a bad folder is refused", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  const open = dialog.getByRole("button", { name: "Open folder" });
  await expect(open).toBeDisabled();
  await dialog.getByLabel("New vault folder").fill("notes");
  await open.click();
  await expect(dialog.getByRole("alert")).toContainText("vault folder not found");
  await dialog.getByLabel("New vault folder").fill("/notes/brain");
  await open.click();
  await expect(dialog.getByRole("status")).toContainText("Opened /notes/brain.");
  await expect(dialog.locator("code").filter({ hasText: "/notes/brain" })).toBeVisible();
});

test("a Claude key is saved and removed under Models and keys", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Models and keys" }).click();
  const row = dialog.getByRole("list", { name: "Saved keys" }).getByRole("listitem").filter({ hasText: "Claude (Anthropic)" });
  await expect(row.getByRole("button", { name: "Remove" })).toHaveCount(0);
  await row.getByLabel("New Claude (Anthropic) key").fill("sk-ant-test-1234");
  await row.getByRole("button", { name: "Save" }).click();
  await expect(row).toContainText("1234");
  await expect(row).not.toContainText("sk-ant-test");
  await row.getByRole("button", { name: "Remove" }).click();
  await expect(row.getByRole("button", { name: "Save" })).toBeVisible();
});

test("Setup removes the index cache only on the second press", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Setup and account" }).click();
  const dialog = page.getByRole("dialog", { name: "Setup" });
  await dialog.getByRole("button", { name: "Remove Hippocampus data" }).click();
  await expect(dialog.getByText("Removed the index cache")).toHaveCount(0);
  await dialog.getByRole("button", { name: "Press again to remove Hippocampus data" }).click();
  await expect(dialog.getByText("Removed the index cache. Your notes are untouched.")).toBeVisible();
});
