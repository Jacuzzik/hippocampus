import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("a dialog takes the keyboard when it opens: Escape closes it and focus goes back", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const opener = page.getByRole("button", { name: "+ Add agent" }).first();
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Add agent" });
  await expect(dialog).toBeVisible();
  // No click inside the dialog: the key must still reach it.
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();
});

test("Tab stays inside an open dialog", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Control panel" }).click();
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(dialog).toBeVisible();
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    const inside = await dialog.evaluate((node) =>
      node.contains(document.activeElement),
    );
    expect(inside, `after ${i + 1} Tab presses`).toBe(true);
  }
});
