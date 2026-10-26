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

test("Ctrl+P lists app actions and Enter runs the one picked", async ({
  page,
}) => {
  const assistant = page.getByLabel("Message the assistant");
  await expect(assistant).toBeVisible();
  await page.keyboard.press("Control+p");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await expect(palette.getByRole("option")).toHaveCount(4);
  await page.keyboard.type("assistant");
  await expect(palette.getByRole("option")).toHaveCount(1);
  await page.keyboard.press("Enter");
  await expect(palette).toHaveCount(0);
  await expect(assistant).toBeHidden();
});

test("the palette's Reset graph view remounts the graph and keeps the drawer", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Alpha" }).click();
  await expect(
    drawer(page).getByRole("heading", { name: "Alpha" }),
  ).toBeVisible();
  await page.keyboard.press("Control+p");
  await page.keyboard.type("reset graph");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("dialog", { name: "Command palette" }),
  ).toHaveCount(0);
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  await expect(
    drawer(page).getByRole("heading", { name: "Alpha" }),
  ).toBeVisible();
});
