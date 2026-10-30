import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the bottom agent bar shows HIPPO with its provider", async ({ page }) => {
  const bar = page.getByLabel("Agents");
  await expect(bar.getByText("HIPPO")).toBeVisible();
  await expect(bar.getByText(/Claude Code|Ollama/)).toBeVisible();
});

test("the bottom agent bar shows a token placeholder until usage is counted", async ({
  page,
}) => {
  await expect(
    page.getByLabel("Agents").getByText("— tokens").first(),
  ).toBeVisible();
});

test("+ Add agent opens the Add agent dialog", async ({ page }) => {
  await page
    .getByLabel("Agents")
    .getByRole("button", { name: "+ Add agent" })
    .click();
  await expect(page.getByRole("dialog", { name: "Add agent" })).toBeVisible();
});

test("the tasks tab opens the task board", async ({ page }) => {
  await page.getByRole("tab", { name: "tasks" }).click();
  await expect(page.getByRole("region", { name: "Tasks" })).toBeVisible();
});

test("the inbox tab lists agent messages", async ({ page }) => {
  await page.getByRole("tab", { name: "inbox" }).click();
  await expect(page.getByRole("region", { name: "Inbox" })).toContainText(
    "Research the plan",
  );
});

test("the settings button opens Munder Difflin's categories", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await expect(dialog).toContainText("Home folder");
  await dialog.getByRole("button", { name: "Agents & Models" }).click();
  await expect(dialog).toContainText("claude · claude-sonnet-5-5");
});

test("each settings category shows only its own options", async ({ page }) => {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("button", { name: "Dictation & Meetings" }).click();
  await expect(dialog).toContainText("Push to talk key");
  await expect(dialog).not.toContainText("Home folder");
});

test("the memory tab lists each agent's notes", async ({ page }) => {
  await page.getByRole("tab", { name: "memory" }).click();
  await expect(page.getByRole("region", { name: "Memory" })).toContainText(
    "kevin",
  );
});

test("INFO opens the card's details and Escape closes them", async ({
  page,
}) => {
  const bar = page.getByLabel("Agents");
  await bar.getByRole("button", { name: "Info" }).first().click();
  const info = page.getByRole("dialog", { name: "HIPPO details" });
  await expect(info.getByText("MODEL")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(info).toHaveCount(0);
});

test("an added agent is still listed after a reload", async ({ page }) => {
  await page
    .getByLabel("Agents")
    .getByRole("button", { name: "+ Add agent" })
    .click();
  const add = page.getByRole("dialog", { name: "Add agent" });
  await add.getByRole("textbox", { name: "Name", exact: true }).fill("Ada");
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Folder", exact: true })
    .fill("/home/me/notes");
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Model", exact: true })
    .fill("claude-sonnet-5-5");
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Goal", exact: true })
    .fill("Tidy the inbox notes");
  await add.getByRole("button", { name: "Spawn" }).click();
  await expect(page.getByLabel("Agents").getByText("Ada")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Agents").getByText("Ada")).toBeVisible();
});
