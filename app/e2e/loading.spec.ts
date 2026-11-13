import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("a tab shows its list once loaded, with no loading placeholder left behind", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  for (const tab of [
    "skills",
    "history",
    "memory",
    "tasks",
    "inbox",
    "monitor",
  ]) {
    await page.getByRole("tab", { name: new RegExp(`^${tab}`) }).click();
    await expect(page.getByRole("status", { name: /^Loading / })).toHaveCount(
      0,
    );
  }
});

test("when a list cannot be read, the placeholder gives way to the reason", async ({
  page,
}) => {
  await mockSidecar(page, { fail: ["skills"] });
  await page.goto("/");
  await page.getByRole("tab", { name: "skills" }).click();
  await expect(page.getByText("Could not read the skills.")).toBeVisible();
  await expect(page.getByRole("status", { name: /^Loading / })).toHaveCount(0);
});

test("the start-up screen lists the real steps and a progress bar", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.addInitScript(() =>
    localStorage.setItem(
      "hippocampus.prefs",
      JSON.stringify({ intro: "long" }),
    ),
  );
  await page.goto("/");
  const steps = page.getByRole("list", { name: "Start-up steps" });
  await expect(steps).toContainText("Notes and graph");
  await expect(steps).toContainText("Agent list");
  await expect(
    page.getByRole("progressbar", { name: "Start-up progress" }),
  ).toBeVisible();
});
