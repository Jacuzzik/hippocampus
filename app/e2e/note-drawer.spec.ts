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

test("an edit keeps the earlier version, which can be shown and restored", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Alpha" }).click();
  const box = drawer(page);
  await box.getByRole("button", { name: "History" }).click();
  const history = box.getByRole("region", { name: "Note history" });
  await expect(history).toContainText("No earlier versions yet");

  await box.getByRole("button", { name: "Edit" }).click();
  await box.getByLabel("Note text").fill("# Alpha\n\nRewritten.\n");
  await box.getByLabel("Note text").blur();
  await box.getByRole("button", { name: "History" }).click();
  await box.getByRole("button", { name: "History" }).click();
  const versions = history.getByRole("list", { name: "Versions" });
  await expect(versions.locator("li")).toHaveCount(1);
  await versions.getByRole("button", { name: "Show" }).click();
  await expect(history.getByLabel("Version text")).toContainText("Steps");

  await versions.getByRole("button", { name: "Restore" }).click();
  await expect(box.getByLabel("Note text")).toHaveValue(/Steps/);
  await expect(versions.locator("li")).toHaveCount(2);
});
