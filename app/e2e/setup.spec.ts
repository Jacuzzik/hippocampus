import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// 7.29: on the very first start, Setup and account opens with the setup checks; never again after that.
test("the first start opens the setup checklist once, with a mark and next step per check", async ({
  page,
}) => {
  await mockSidecar(page, { firstRun: true });
  await page.goto("/");
  const dialog = page.getByRole("dialog", { name: "Setup and account" });
  const list = dialog.getByRole("list", { name: "Setup checks" });
  await expect(list.getByRole("listitem")).toHaveCount(3);
  await expect(dialog.getByText("1 of 3 ready.")).toBeVisible();
  await expect(
    list.getByRole("listitem").filter({ hasText: "Codex program" }),
  ).toContainText("✗");
  await expect(
    list.getByRole("listitem").filter({ hasText: "Backend" }),
  ).toContainText("✓");
  await dialog.getByRole("button", { name: "Check again" }).click();
  await expect(dialog.getByText("1 of 3 ready.")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("Agents").getByText("HIPPO")).toBeVisible();
  await expect(dialog).toHaveCount(0);
});
