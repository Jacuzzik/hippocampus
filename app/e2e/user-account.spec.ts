import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// The Hippocampus account (14.11, 14.12, M.22) in Settings > General.

test("the Account section is hidden until the build has the sign-in service", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await expect(dialog.getByText("Vault folder")).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "Account" })).toHaveCount(0);
});

test("sign in with Google, choose consent, sign out", async ({ page }) => {
  await mockSidecar(page, { account: true });
  await page.goto("/");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await expect(dialog.getByRole("heading", { name: "Account" })).toBeVisible();

  await dialog.getByRole("button", { name: "Sign in with Google" }).click();
  await expect(
    dialog.getByText("Finish signing in in your browser"),
  ).toBeVisible();
  await page.evaluate(() =>
    (window as unknown as { __finishSignIn: () => void }).__finishSignIn(),
  );
  await expect(dialog.getByText("Ada", { exact: true })).toBeVisible({
    timeout: 5000,
  });
  await expect(dialog.getByText("Plan: Free")).toBeVisible();

  // Consent asks once, with both choices off.
  const consent = dialog.getByRole("group", {
    name: "Before anything leaves this computer",
  });
  await expect(
    consent.getByLabel("Sync settings and briefings"),
  ).not.toBeChecked();
  await expect(consent.getByLabel("Send usage reports")).not.toBeChecked();
  await consent.getByRole("button", { name: "Save choices" }).click();
  await expect(consent).toHaveCount(0);

  // Deleting needs a second click.
  await dialog.getByRole("button", { name: "Delete account" }).click();
  await expect(
    dialog.getByRole("button", { name: "Yes, delete my account" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Keep it" }).click();

  await dialog.getByRole("button", { name: "Sign out" }).click();
  await expect(
    dialog.getByRole("button", { name: "Sign in with Google" }),
  ).toBeVisible();
});
