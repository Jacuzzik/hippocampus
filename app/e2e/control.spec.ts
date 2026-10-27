import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

async function openControl(page: import("@playwright/test").Page): Promise<void> {
  await page.getByRole("button", { name: "Control panel" }).click();
}

test("the control panel opens from the ribbon and lists every panel", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  for (const heading of [
    "Network",
    "Token budget",
    "Ask me",
    "Activity log",
    "Memory search",
    "Scheduled notes jobs",
    "Helper jobs",
    "Share a note by password link",
    "Skills",
    "Keys and secrets",
  ]) {
    await expect(dialog.getByRole("heading", { name: heading })).toBeVisible();
  }
});

test("network starts Off and a chosen mode is kept", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  const group = dialog.getByRole("group", { name: "Network mode" });
  await expect(group.getByRole("button", { name: "Off" })).toHaveAttribute("aria-pressed", "true");
  await group.getByRole("button", { name: "Converse" }).click();
  await expect(group.getByRole("button", { name: "Converse" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("activity filters by kind and shows who approved a change", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await dialog.getByRole("button", { name: "Approvals" }).click();
  await expect(dialog.getByText("approved by you on the approval card")).toBeVisible();
  await expect(dialog.getByText("network is Off")).toHaveCount(0);
});

test("share says Not set up and a helper cannot be started empty", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(dialog.getByRole("button", { name: "Start helper" })).toBeDisabled();
  await dialog.getByLabel("Link password").fill("long enough password");
  await dialog.getByRole("button", { name: "Make link" }).click();
  await expect(dialog.getByRole("alert")).toContainText("Not set up");
});
