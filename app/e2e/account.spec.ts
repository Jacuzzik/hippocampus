import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("with no brain open, setup opens first and a brain opens the graph", async ({
  page,
}) => {
  await mockSidecar(page, { noVault: true });
  await page.goto("/");
  const dialog = page.getByRole("dialog", { name: "Setup and account" });
  await expect(dialog).toBeVisible();
  await page.getByLabel("Brain folder path").fill("/notes/brain");
  await page.getByRole("button", { name: "Open brain" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
});

test("sign in saves the key and sign out needs a second press", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Setup and account" }).click();
  const dialog = page.getByRole("dialog", { name: "Setup and account" });
  await expect(dialog.getByText("Not signed in")).toBeVisible();

  await dialog.getByLabel("Claude API key").fill("sk-ant-test");
  await dialog.getByRole("button", { name: "Sign in" }).click();
  await expect(dialog.getByText("Signed in to Claude")).toBeVisible();
  await expect(dialog.getByLabel("Claude API key")).toHaveCount(0);

  await dialog.getByRole("button", { name: "Sign out" }).click();
  await expect(dialog.getByText("Signed in to Claude")).toBeVisible();
  await dialog.getByRole("button", { name: "Press again to sign out" }).click();
  await expect(dialog.getByText("Not signed in")).toBeVisible();
});

test("a saved key shows signed in at start", async ({ page }) => {
  await mockSidecar(page, { signedIn: true });
  await page.goto("/");
  await page.getByRole("button", { name: "Setup and account" }).click();
  await expect(
    page
      .getByRole("dialog", { name: "Setup and account" })
      .getByText("Signed in to Claude"),
  ).toBeVisible();
});
