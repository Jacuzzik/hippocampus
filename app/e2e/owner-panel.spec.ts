import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the bottom agent bar shows HIPPO with its provider", async ({ page }) => {
  const bar = page.getByLabel("Agents");
  await expect(bar.getByText("HIPPO")).toBeVisible();
  // The provider is shown in the HIPPO details (INFO), not on the bar.
  await bar.getByRole("button", { name: "Info", exact: true }).first().click();
  const info = page.getByRole("dialog", { name: "Hippoherman details" });
  await expect(info.getByText(/Claude|Ollama/)).toBeVisible();
  await page.keyboard.press("Escape");
});

test("the bottom agent bar shows a token placeholder until usage is counted", async ({
  page,
}) => {
  // The bar shows no token count until usage is reported; the HIPPO details still say so.
  const info = page
    .getByLabel("Agents")
    .getByRole("button", { name: "Info", exact: true })
    .first();
  await info.click();
  await expect(
    page
      .getByRole("dialog", { name: "Hippoherman details" })
      .getByText("—")
      .first(),
  ).toBeVisible();
  await page.keyboard.press("Escape");
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
  await bar.getByRole("button", { name: "Info", exact: true }).first().click();
  const info = page.getByRole("dialog", { name: "Hippoherman details" });
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
  await add.getByLabel("Folder in workspaces").selectOption("IT");
  await add.getByRole("button", { name: "Next" }).click();
  await add.getByRole("button", { name: "claude-sonnet-5-5" }).click();
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Goal", exact: true })
    .fill("Tidy the inbox notes");
  await add.getByRole("button", { name: "Spawn" }).click();
  await expect(page.getByLabel("Agents").getByText("Ada")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Agents").getByText("Ada")).toBeVisible();
});

test("a card menu archives an added agent and the Control panel restores it", async ({
  page,
}) => {
  const bar = page.getByLabel("Agents");
  await bar.getByRole("button", { name: "+ Add agent" }).click();
  const add = page.getByRole("dialog", { name: "Add agent" });
  await add.getByRole("textbox", { name: "Name", exact: true }).fill("Grace");
  await add.getByRole("button", { name: "Next" }).click();
  await add.getByLabel("Folder in workspaces").selectOption("IT");
  await add.getByRole("button", { name: "Next" }).click();
  await add.getByRole("button", { name: "claude-sonnet-5-5" }).click();
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Goal", exact: true })
    .fill("Tidy the notes");
  await add.getByRole("button", { name: "Spawn" }).click();
  await bar
    .getByRole("button", { name: "Grace options" })
    .click({ button: "right" });
  await page.getByRole("menuitem", { name: "Archive" }).click();
  await expect(bar.getByText("Grace")).toHaveCount(0);
  await page.getByRole("button", { name: "Control panel" }).click();
  const control = page.getByRole("dialog", { name: "Control panel" });
  await control.getByRole("tab", { name: "Team and sharing" }).click();
  await control.getByRole("button", { name: "Restore" }).click();
  await expect(bar.getByText("Grace")).toBeVisible();
});
