import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

const drawer = (page: import("@playwright/test").Page) =>
  page.getByRole("complementary", { name: "Note details" });

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
});

test("the drawer renders the note as Markdown and follows a wikilink", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Alpha" }).click();
  const body = drawer(page).getByRole("region", { name: "Note text" });
  await expect(body.getByRole("heading", { name: "Alpha" })).toHaveCount(0);
  await expect(body.getByRole("heading", { name: "Steps" })).toBeVisible();
  await expect(body.locator("li")).toHaveCount(2);
  await expect(body.getByRole("link", { name: "docs" })).toHaveAttribute(
    "href",
    "https://example.com",
  );
  await expect(body.locator("pre code")).toContainText("let x = 1;");

  await body.getByRole("button", { name: "the last note" }).click();
  await expect(
    drawer(page).getByRole("heading", { name: "Gamma" }),
  ).toBeVisible();
  await expect(drawer(page).getByText("No links here.")).toBeVisible();
});
