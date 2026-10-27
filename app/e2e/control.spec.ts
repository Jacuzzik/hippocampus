import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

async function openControl(
  page: import("@playwright/test").Page,
): Promise<void> {
  await page.getByRole("button", { name: "Control panel" }).click();
}

test("the control panel opens from the ribbon and lists every panel", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  for (const heading of [
    "Network",
    "Token budget",
    "Ask me",
    "Activity log",
    "Memory search",
    "Scheduled notes jobs",
    "Helper jobs",
    "Share a note by password link",
    "Skills",
    "Keys and secrets",
    "Triggers",
    "Add an agent",
    "Dispatch",
    "Capabilities",
    "Teams",
  ]) {
    await expect(dialog.getByRole("heading", { name: heading })).toBeVisible();
  }
});

test("network starts Off and a chosen mode is kept", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  const group = dialog.getByRole("group", { name: "Network mode" });
  await expect(group.getByRole("button", { name: "Off" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await group.getByRole("button", { name: "Converse" }).click();
  await expect(group.getByRole("button", { name: "Converse" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("activity filters by kind and shows who approved a change", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await dialog.getByRole("button", { name: "Approvals" }).click();
  await expect(
    dialog.getByText("approved by you on the approval card"),
  ).toBeVisible();
  await expect(dialog.getByText("network is Off")).toHaveCount(0);
});

test("share says Not set up and a helper cannot be started empty", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(
    dialog.getByRole("button", { name: "Start helper" }),
  ).toBeDisabled();
  await dialog.getByLabel("Link password").fill("long enough password");
  await dialog.getByRole("button", { name: "Make link" }).click();
  await expect(dialog.getByRole("alert")).toContainText("Not set up");
});

test("the budget has a 5-hour cap next to day, week and month", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(dialog.getByLabel("Assistant 5 hours cap")).toHaveValue("20000");
  await expect(dialog.getByLabel("Whole app day cap")).toHaveValue("200000");
});

test("triggers show the network, the job count and that compaction is Not set up", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(dialog.getByText("1 set, 1 on")).toBeVisible();
  await expect(
    dialog.getByText("Not set up: the assistant does not shorten"),
  ).toBeVisible();
  await expect(dialog.getByText("None. Webhooks are not set up")).toBeVisible();
});

test("scheduled jobs show how many are on", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(dialog.getByText("1 of 1 on.")).toBeVisible();
});

test("add an agent stops at each step until it is answered", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  const add = dialog.locator("#control-add-agent").locator("..");
  await add.getByRole("button", { name: "Next" }).click();
  await expect(add.getByRole("alert")).toHaveText("Give the agent a name.");
  await add.getByRole("textbox", { name: "Name", exact: true }).fill("Ada");
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Folder", exact: true })
    .fill("/home/me/notes");
  await add.getByRole("button", { name: "Next" }).click();
  await expect(add.getByRole("status")).toHaveText(
    "Not set up: no Claude (Anthropic) key saved.",
  );
  await add
    .getByRole("textbox", { name: "Model", exact: true })
    .fill("claude-sonnet-5-5");
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Goal", exact: true })
    .fill("Tidy the inbox notes");
  await expect(
    add.getByRole("button", { name: "Create agent: Not set up" }),
  ).toBeDisabled();
});

test("the engine is ready once a Claude key is saved", async ({ page }) => {
  await mockSidecar(page, { signedIn: true });
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  const add = dialog.locator("#control-add-agent").locator("..");
  await add.getByRole("textbox", { name: "Name", exact: true }).fill("Ada");
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Folder", exact: true })
    .fill("/home/me/notes");
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Model", exact: true })
    .fill("claude-sonnet-5-5");
  await expect(add.getByRole("status")).toHaveText(
    "Ready: Claude (Anthropic) key saved.",
  );
});

test("a dispatch is sent only after the confirm card", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await dialog.getByRole("button", { name: "Review and send" }).click();
  await expect(dialog.getByRole("alert")).toHaveText("Write the task.");
  await dialog.getByLabel("Task").fill("Tidy the inbox notes");
  await dialog.getByRole("button", { name: "Review and send" }).click();
  const card = dialog.getByRole("alertdialog", { name: "Confirm dispatch" });
  await expect(card).toContainText("Tidy the inbox notes");
  await card.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog.getByText("Sent to helper.")).toHaveCount(0);
  await dialog.getByRole("button", { name: "Review and send" }).click();
  await dialog
    .getByRole("alertdialog", { name: "Confirm dispatch" })
    .getByRole("button", { name: "Send" })
    .click();
  await expect(dialog.getByText("Sent to helper.")).toBeVisible();
});

test("teams say Not enrolled and cannot start a team here", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(dialog.getByText("Status: Not enrolled")).toBeVisible();
  await dialog.getByRole("button", { name: "Start a team" }).click();
  await expect(dialog.getByRole("status")).toContainText("Not set up");
});

test("capabilities list the skills and show install as Not set up", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  const caps = dialog.locator("#control-capabilities").locator("..");
  await expect(caps.getByText("tidy-notes")).toBeVisible();
  await expect(
    caps.getByRole("button", { name: "Install: Not set up" }).first(),
  ).toBeDisabled();
});
