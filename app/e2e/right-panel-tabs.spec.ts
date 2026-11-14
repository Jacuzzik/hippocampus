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

test("the history tab can be searched", async ({ page }) => {
  await page.getByRole("tab", { name: "history" }).click();
  const region = page.getByRole("region", { name: "History" });
  await expect(region).toContainText("paused: assistant daily cap reached");
  await region
    .getByRole("searchbox", { name: "Search history" })
    .fill("nomatch-zzz");
  await expect(region).not.toContainText("paused: assistant daily cap reached");
  await expect(region).toContainText('No event matches "nomatch-zzz"');
  await region
    .getByRole("searchbox", { name: "Search history" })
    .fill("DAILY cap");
  await expect(region).toContainText("paused: assistant daily cap reached");
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

test("the skills tab can be searched by name or by what a skill does", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "skills" }).click();
  const region = page.getByRole("region", { name: "Skills" });
  const find = region.getByLabel("Search skills");
  await find.fill("TIDY");
  await expect(region).toContainText("tidy-notes");
  await find.fill("note list");
  await expect(region).toContainText("tidy-notes");
  await find.fill("zebra");
  await expect(region).not.toContainText("tidy-notes");
  await expect(region).toContainText('No skill matches "zebra".');
});

test("the activity tab filters by kind and by a word, and can be paused", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "activity" }).click();
  const region = page.getByRole("region", { name: "Activity" });
  await expect(region).toContainText("search_notes");
  await region.getByLabel("Filter by kind").selectOption("approval");
  await expect(region).not.toContainText("search_notes");
  await expect(region).toContainText("create_note");
  await region.getByLabel("Filter by kind").selectOption("all");
  await region.getByLabel("Search activity").fill("zzzz");
  await expect(region).toContainText("Nothing matches.");
  await region.getByLabel("Search activity").fill("");
  await region.getByRole("checkbox", { name: "Pause" }).check();
  await expect(region.getByRole("checkbox", { name: "Pause" })).toBeChecked();
});

test("the activity tab limits rows to a date range", async ({ page }) => {
  await page.getByRole("tab", { name: "activity" }).click();
  const region = page.getByRole("region", { name: "Activity" });
  await expect(region).toContainText("search_notes");
  await region.getByLabel("From date").fill("2026-10-28");
  await expect(region).toContainText("Nothing matches.");
  await region.getByLabel("From date").fill("2026-10-27");
  await region.getByLabel("To date").fill("2026-10-27");
  await expect(region).toContainText("search_notes");
  await region.getByLabel("To date").fill("2026-10-26");
  await expect(region).toContainText("Nothing matches.");
});

test("the memory tab shows a size meter against the cap and warns near it", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "memory" }).click();
  const region = page.getByRole("region", { name: "Memory" });
  await expect(region.getByLabel("god memory size")).toHaveAttribute(
    "max",
    "32000",
  );
  await expect(region).toContainText("4.0 of 31.3 KB");
  await expect(region).toContainText("Nearly full");
});

test("the activity tab reads again when the backend says the log changed, without waiting for a timer", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "activity" }).click();
  const region = page.getByRole("region", { name: "Activity" });
  await expect(region).toContainText("search_notes");
  await expect(region).not.toContainText("pushed by an event");
  await page.evaluate(() => {
    const w = window as unknown as {
      __newActivity?: boolean;
      __sidecarEvent?: (payload: unknown) => void;
    };
    w.__newActivity = true;
    w.__sidecarEvent?.({ event: "changed", what: "activity" });
  });
  // The safety-net timer is 30 seconds; this passes in well under that only because of the event.
  await expect(region).toContainText("pushed by an event", { timeout: 3000 });
});

test("a temp is started from the temps tab and shows in the list as running", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "temps" }).click();
  const region = page.getByRole("region", { name: "Temps" });
  const start = region.getByRole("button", { name: "Start temp" });
  await expect(start).toBeDisabled();
  await region
    .getByLabel("What the temp should do")
    .fill("Summarise the note Alpha");
  await start.click();
  await expect(region.getByRole("listitem").last()).toContainText(
    "Summarise the note Alpha",
  );
  await expect(region.getByRole("listitem").last()).toContainText("running");
  await expect(region.getByLabel("What the temp should do")).toHaveValue("");
});

test("an answered question moves to the answered list with what was said", async ({
  page,
}) => {
  await page.getByRole("tab", { name: /^ask me/ }).click();
  const answer = page.getByLabel(/^Answer: Which folder/);
  await answer.fill("ideas");
  await answer.press("Enter");
  const done = page.getByRole("list", { name: "Answered questions" });
  await expect(done).toContainText("Which folder should the new note go in?");
  await expect(done).toContainText("ideas");
});

test("a skill is installed from a folder and removed in the skills tab, each with a second click to confirm", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "skills" }).click();
  const region = page.getByRole("region", { name: "Skills" });
  await region.getByLabel("Skill folder to install").fill("/home/me/new-skill");
  await region.getByRole("button", { name: "Install" }).click();
  await expect(region.getByText("new-skill")).toHaveCount(0); // the first click only asks
  await region.getByRole("button", { name: "Confirm install" }).click();
  await expect(region.getByText("new-skill")).toBeVisible();
  await region.getByRole("button", { name: "Remove new-skill" }).click();
  await expect(region.getByText("new-skill")).toBeVisible();
  await region
    .getByRole("button", { name: "Confirm: remove new-skill" })
    .click();
  await expect(region.getByText("new-skill")).toHaveCount(0);
});
