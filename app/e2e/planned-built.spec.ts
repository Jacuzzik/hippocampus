import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// Features that were Planned cards and are now built.
async function settingsPage(
  page: import("@playwright/test").Page,
  tab: string,
) {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: tab, exact: true }).click();
  return dialog;
}

test("the update check is off until turned on, then shows what's new (G.04)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "General");
  const check = dialog.getByRole("button", { name: "Check now" });
  await expect(check).toBeDisabled();
  await dialog.getByRole("checkbox", { name: "Check for updates" }).check();
  await check.click();
  await expect(
    dialog.getByRole("status").filter({ hasText: "v0.2.0 is out" }),
  ).toBeVisible();
  await expect(dialog.getByText("Faster graph.")).toBeVisible();
});

test("a calendar link and Notion connect on the Connectors page", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "Connectors");
  const calendar = dialog.getByRole("region", {
    name: "Calendar",
    exact: true,
  });
  const notion = dialog.getByRole("region", { name: "Notion", exact: true });
  await calendar
    .getByLabel("Secret iCal address")
    .fill("https://calendar.google.com/x/basic.ics");
  await calendar.getByRole("button", { name: "Connect" }).click();
  await expect(
    calendar.getByRole("list", { name: "Calendar events" }),
  ).toContainText("Stand-up");
  await notion.getByLabel("Notion secret").fill("ntn_" + "x".repeat(30));
  await notion.getByRole("button", { name: "Connect" }).click();
  await notion.getByRole("button", { name: "Search", exact: true }).click();
  await notion.getByRole("button", { name: "Read into a note" }).click();
  await expect(notion.getByText("Saved to Notion/Roadmap.md")).toBeVisible();
});

test("search by meaning builds an index and finds a note (7.09)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "Memory");
  await dialog.getByRole("button", { name: "Build the index" }).click();
  await expect(dialog.getByText("12 notes in the index.")).toBeVisible();
  await dialog
    .getByRole("textbox", { name: "Search by meaning" })
    .fill("the app plan");
  const meaning = dialog.getByRole("region", { name: "Search by meaning" });
  await meaning.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    dialog.getByRole("list", { name: "Closest notes" }),
  ).toContainText("Projects/Hippocampus.md");
});

test("a plugin is added from a zip and can be switched off (D.07)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "Helpers and skills");
  await dialog.getByLabel("Plugin file").setInputFiles({
    name: "writer.zip",
    mimeType: "application/zip",
    buffer: Buffer.from("PK"),
  });
  const list = dialog.getByRole("list", { name: "Plugins" });
  await expect(list).toContainText("writer");
  await list.getByRole("checkbox", { name: "Use writer" }).uncheck();
  await expect(list.getByText("Off")).toBeVisible();
});
