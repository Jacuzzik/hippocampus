import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("a graph lens is picked from the toolbar and kept for the next start", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  const lens = page.getByLabel("Graph lens");
  await expect(lens).toHaveValue("notes");
  await lens.selectOption("activity");
  await page.reload();
  await expect(page.getByLabel("Graph lens")).toHaveValue("activity");
});
