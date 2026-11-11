import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

async function openSettings(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Control panel" }).click();
  await page
    .getByRole("dialog", { name: "Control panel" })
    .getByRole("button", { name: "Open settings" })
    .click();
  return page.getByRole("dialog", { name: "Settings" });
}

test("settings has a page per category and each one opens", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  const pages: Record<string, string> = {
    General: "Vault folder",
    Appearance: "Terminal text size",
    Agents: "Main agent engine",
    Budgets: "Token budget",
    "Models and keys": "Keys and secrets",
    Connectors: "Working on this computer",
    Memory: "Memory size per agent",
    "Privacy and data": "UI error log",
    Advanced: "Backend (Python sidecar)",
    About: "Hippocampus",
  };
  await expect(dialog.getByRole("tab")).toHaveText(Object.keys(pages));
  for (const [name, text] of Object.entries(pages)) {
    await dialog.getByRole("tab", { name, exact: true }).click();
    await expect(dialog.getByRole("tabpanel").getByText(text, { exact: true }).first()).toBeVisible();
  }
});

test("the terminal text size is kept between 10 and 20 and survives a reload", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  let dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Appearance" }).click();
  await dialog.getByRole("button", { name: "Larger terminal text" }).click();
  await expect(dialog.getByText("13px")).toBeVisible();
  for (let i = 0; i < 10; i++) {
    const smaller = dialog.getByRole("button", { name: "Smaller terminal text" });
    if (await smaller.isDisabled()) break;
    await smaller.click();
  }
  await expect(dialog.getByText("10px")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Smaller terminal text" })).toBeDisabled();
  await page.reload();
  dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Appearance" }).click();
  await expect(dialog.getByText("10px")).toBeVisible();
});

test("a connector that is not built yet is a Planned card with its reason", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Connectors" }).click();
  const slack = dialog.getByRole("article").filter({ hasText: "Slack" });
  await expect(slack).toContainText("Planned");
  await expect(slack).toContainText("Needs a token store");
  await expect(dialog.getByRole("article").filter({ hasText: "Webhooks" }).first()).toContainText("0 webhooks saved.");
});

test("searching settings jumps to the matching page", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByLabel("Search settings").fill("slack");
  await expect(dialog.getByRole("tab")).toHaveText(["Connectors"]);
  await expect(dialog.getByRole("heading", { name: "Connectors" })).toBeVisible();
});
