import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

const drawer = (page: import("@playwright/test").Page) =>
  page.getByRole("complementary", { name: "Note details" });

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
});

test("Ctrl+O fuzzy-finds a note and Enter opens it in the drawer", async ({
  page,
}) => {
  await page.keyboard.press("Control+o");
  const box = page.getByRole("dialog", { name: "Quick switcher" });
  await expect(box).toBeVisible();
  await page.keyboard.type("gm");
  await expect(box.getByRole("option")).toHaveCount(1);
  await page.keyboard.press("Enter");
  await expect(box).toHaveCount(0);
  await expect(
    drawer(page).getByRole("heading", { name: "Gamma" }),
  ).toBeVisible();
});
