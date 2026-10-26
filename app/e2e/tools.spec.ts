import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

async function openTools(page: import("@playwright/test").Page): Promise<void> {
  await page.keyboard.press("Control+p");
  await page.getByText("Assistant tools", { exact: true }).click();
}

test("an unticked tool stays off the assistant's list after reopening", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openTools(page);
  const dialog = page.getByRole("dialog", { name: "Assistant tools" });
  await dialog.getByLabel("Every tool").uncheck();
  await dialog.getByLabel(/read_note/).uncheck();
  await expect(dialog.getByLabel(/read_note/)).not.toBeChecked();
  await expect(dialog.getByLabel(/create_note/)).toBeChecked();

  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await openTools(page);
  await expect(
    page
      .getByRole("dialog", { name: "Assistant tools" })
      .getByLabel(/read_note/),
  ).not.toBeChecked();
});
