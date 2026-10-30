import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the activity tab lists tool runs and approvals", async ({ page }) => {
  await page.getByRole("tab", { name: "activity" }).click();
  const region = page.getByRole("region", { name: "Activity" });
  await expect(region).toContainText("search_notes");
  await expect(region).toContainText("approved");
});

test("the history tab lists past events but not tool runs", async ({ page }) => {
  await page.getByRole("tab", { name: "history" }).click();
  const region = page.getByRole("region", { name: "History" });
  await expect(region).toContainText("paused: assistant daily cap reached");
  await expect(region).not.toContainText("search_notes");
});

test("the skills tab lists installed skills", async ({ page }) => {
  await page.getByRole("tab", { name: "skills" }).click();
  await expect(page.getByRole("region", { name: "Skills" })).toContainText("tidy-notes");
});

test("the temps tab lists helper jobs with their status", async ({ page }) => {
  await page.getByRole("tab", { name: "temps" }).click();
  const region = page.getByRole("region", { name: "Temps" });
  await expect(region).toContainText("Summarise the project notes");
  await expect(region).toContainText("done");
});

test("the right panel tabs save screenshots when SHOTS_DIR is set", async ({ page }) => {
  test.skip(!process.env.SHOTS_DIR, "SHOTS_DIR not set");
  for (const name of ["activity", "history", "skills", "temps"]) {
    await page.getByRole("tab", { name }).click();
    await page.screenshot({ path: `${process.env.SHOTS_DIR}/${name}.png` });
  }
});

test("the monitor tab lists the background watchers with their status", async ({ page }) => {
  await page.getByRole("tab", { name: "monitor" }).click();
  const region = page.getByRole("region", { name: "Monitor" });
  await expect(region).toContainText("Watchers");
  await expect(region).toContainText("CPU");
  await expect(region).toContainText("42%");
  await expect(region).toContainText("Weekly link check");
  await expect(region).toContainText("trigger");
});
