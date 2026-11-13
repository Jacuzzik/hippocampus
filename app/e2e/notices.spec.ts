import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("a failed action is said on screen, once, and can be dismissed", async ({
  page,
}) => {
  await mockSidecar(page, { fail: ["provider_status"] });
  await page.goto("/");
  await page.getByRole("button", { name: "Add agent" }).first().click();
  const notice = page.getByRole("alert", { name: "Problems" });
  await expect(notice).toContainText("Could not check the CLI logins.");
  await expect(notice).toContainText("provider_status is set to fail");
  await notice.getByRole("button", { name: "Dismiss" }).first().click();
  await expect(notice).not.toContainText("Could not check the CLI logins.");
});

test("with nothing wrong there is no notice", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Add agent" }).first().click();
  await expect(page.getByRole("dialog", { name: /agent/i })).toBeVisible();
  await expect(
    page.getByRole("alert", { name: "Problems" }).locator(".notice"),
  ).toHaveCount(0);
});
