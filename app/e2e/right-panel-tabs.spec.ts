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

test("the history tab lists past events but not tool runs", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "history" }).click();
  const region = page.getByRole("region", { name: "History" });
  await expect(region).toContainText("paused: assistant daily cap reached");
  await expect(region).not.toContainText("search_notes");
});

test("the skills tab lists installed skills", async ({ page }) => {
  await page.getByRole("tab", { name: "skills" }).click();
  await expect(page.getByRole("region", { name: "Skills" })).toContainText(
    "tidy-notes",
  );
});

test("the temps tab lists helper jobs with their status", async ({ page }) => {
  await page.getByRole("tab", { name: "temps" }).click();
  const region = page.getByRole("region", { name: "Temps" });
  await expect(region).toContainText("Summarise the project notes");
  await expect(region).toContainText("done");
});

test("the right panel tabs save screenshots when SHOTS_DIR is set", async ({
  page,
}) => {
  test.skip(!process.env.SHOTS_DIR, "SHOTS_DIR not set");
  for (const name of ["activity", "history", "skills", "temps"]) {
    await page.getByRole("tab", { name }).click();
    await page.screenshot({ path: `${process.env.SHOTS_DIR}/${name}.png` });
  }
});

test("the monitor tab lists the agents, the month's token use and the agent folders", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "monitor" }).click();
  const region = page.getByRole("region", { name: "Monitor" });
  await expect(region).toContainText(/agents/i);
  await expect(region).toContainText("Hippoherman");
  await expect(region).toContainText("tok burned this month");
  await expect(region).toContainText(/directories/i);
});

test("the tabs show how many questions and inbox messages are waiting", async ({
  page,
}) => {
  await expect(page.getByRole("tab", { name: "ask me" })).toContainText("1");
  await expect(page.getByRole("tab", { name: "inbox" })).toContainText("1");
  await expect(page.getByRole("tab", { name: "tasks" })).toHaveText("tasks");
});

test("arrow keys move between the Control Room tabs", async ({ page }) => {
  const terminal = page.getByRole("tab", { name: "terminal" });
  await terminal.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "monitor" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "temps" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.keyboard.press("Home");
  await expect(terminal).toHaveAttribute("aria-selected", "true");
});

test("a tab already opened stays mounted when you leave it", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "skills" }).click();
  const region = page.getByRole("region", { name: "Skills" });
  await expect(region).toContainText("tidy-notes");
  // Mark the live element; a remount would drop the mark.
  await region.evaluate((el) => el.setAttribute("data-kept", "yes"));
  await page.getByRole("tab", { name: "activity" }).click();
  await expect(region).toBeHidden();
  await page.getByRole("tab", { name: "skills" }).click();
  await expect(region).toHaveAttribute("data-kept", "yes");
});

test("a tab never opened is not mounted", async ({ page }) => {
  await expect(page.getByRole("region", { name: "Skills" })).toHaveCount(0);
});
