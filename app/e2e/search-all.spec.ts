import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("Ctrl+Shift+F searches notes, messages and agents, and opens a note", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  await page.keyboard.press("Control+Shift+F");
  const box = page.getByRole("combobox", { name: "Search everything" });
  await box.fill("alpha");
  const results = page.getByRole("listbox", { name: "Results" });
  await expect(results).toContainText("Notes");
  await expect(results.getByRole("option").first()).toContainText("alpha");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("complementary", { name: "Note details" }),
  ).toBeVisible();

  await page.keyboard.press("Control+Shift+F");
  await page
    .getByRole("combobox", { name: "Search everything" })
    .fill("release");
  await expect(page.getByRole("listbox", { name: "Results" })).toContainText(
    "Release notes",
  );
  await page.getByRole("combobox", { name: "Search everything" }).fill("zzzz");
  await expect(page.getByRole("listbox", { name: "Results" })).toContainText(
    "No matches.",
  );
});
