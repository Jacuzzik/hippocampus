import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

async function openControl(
  page: import("@playwright/test").Page,
): Promise<void> {
  await page.getByRole("button", { name: "Control panel" }).click();
}

test("the control panel opens from the ribbon and each tab lists its panels", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  const tabs: Record<string, string[]> = {
    Overview: ["Network", "Activity log"],
    Work: ["Dispatch", "Scheduled notes jobs", "Triggers"],
    Questions: ["Ask me"],
    "Helpers and skills": ["Helper jobs", "Capabilities", "Skills"],
    "Team and sharing": ["Teams", "Share a note by password link"],
  };
  await expect(dialog.getByRole("tab")).toHaveText(Object.keys(tabs));
  for (const [name, headings] of Object.entries(tabs)) {
    await dialog.getByRole("tab", { name }).click();
    for (const heading of headings) {
      // Some headings carry a status badge, so match the start of the name.
      await expect(dialog.getByRole("heading", { name: new RegExp(`^${heading}`) })).toBeVisible();
    }
  }
});

test("arrow keys move between the control panel tabs", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await dialog.getByRole("tab", { name: "Overview" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(dialog.getByRole("tab", { name: "Work" })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("End");
  await expect(dialog.getByRole("tab", { name: "Team and sharing" })).toHaveAttribute("aria-selected", "true");
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
  await dialog.getByRole("tab", { name: "Helpers and skills" }).click();
  await expect(
    dialog.getByRole("button", { name: "Start helper" }),
  ).toBeDisabled();
  await dialog.getByRole("tab", { name: "Team and sharing" }).click();
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
  await page
    .getByRole("dialog", { name: "Control panel" })
    .getByRole("button", { name: "Open settings" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Budgets" }).click();
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
  await dialog.getByRole("tab", { name: "Work" }).click();
  await expect(dialog.getByText("1 set, 1 on")).toBeVisible();
  await expect(
    dialog.getByText("Not set up: the assistant does not shorten"),
  ).toBeVisible();
  await expect(dialog.getByText("None saved yet.")).toBeVisible();
});

test("scheduled jobs show how many are on", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await dialog.getByRole("tab", { name: "Work" }).click();
  await expect(dialog.getByText("1 of 1 on.")).toBeVisible();
});

test("add an agent stops at each step until it is answered", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page
    .getByLabel("Agents")
    .getByRole("button", { name: "+ Add agent" })
    .click();
  const add = page.getByRole("dialog", { name: "Add agent" });
  await add.getByRole("button", { name: "Next" }).click();
  await expect(add.getByRole("alert")).toHaveText("Give the agent a name.");
  await add.getByRole("textbox", { name: "Name", exact: true }).fill("Ada");
  await add.getByRole("button", { name: "Next" }).click();

  // The folder step: nothing is chosen yet, then a new folder is made inside workspaces.
  await add.getByRole("button", { name: "Next" }).click();
  await expect(add.getByRole("alert")).toHaveText(
    "Choose the folder the agent works in.",
  );
  await add.getByLabel("New folder inside workspaces").fill("ada");
  await add.getByRole("button", { name: "Create folder" }).click();
  await add.getByRole("button", { name: "Next" }).click();

  // The engine step: no key is saved, and a model has to be picked.
  await expect(
    add.getByText("Not set up: no Claude (Anthropic) key saved."),
  ).toBeVisible();
  await add.getByRole("button", { name: "Next" }).click();
  await expect(add.getByRole("alert")).toHaveText("Name the model.");
  await add.getByRole("button", { name: "claude-sonnet-5-5" }).click();
  await expect(add.locator("code")).toContainText("claude-sonnet-5-5");
  await add.getByRole("button", { name: "Next" }).click();

  await add
    .getByRole("textbox", { name: "Goal", exact: true })
    .fill("Tidy the inbox notes");
  await add.getByRole("button", { name: "Spawn" }).click();
  await expect(add).toHaveCount(0);
  await expect(page.getByLabel("Agents").getByText("Ada")).toBeVisible();
});

test("the engine is ready once a Claude key is saved", async ({ page }) => {
  await mockSidecar(page, { signedIn: true });
  await page.goto("/");
  await page
    .getByLabel("Agents")
    .getByRole("button", { name: "+ Add agent" })
    .click();
  const add = page.getByRole("dialog", { name: "Add agent" });
  await add.getByRole("textbox", { name: "Name", exact: true }).fill("Ada");
  await add.getByRole("button", { name: "Next" }).click();
  await add.getByLabel("Folder in workspaces").selectOption("IT");
  await add.getByRole("button", { name: "Next" }).click();
  await expect(
    add.getByText("Ready: Claude (Anthropic) key saved."),
  ).toBeVisible();
});

test("a dispatch is sent only after the confirm card", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await dialog.getByRole("tab", { name: "Work" }).click();
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
  await dialog.getByRole("tab", { name: "Team and sharing" }).click();
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
  await dialog.getByRole("tab", { name: "Helpers and skills" }).click();
  const caps = dialog.locator("#control-capabilities").locator("..");
  await expect(caps.getByText("tidy-notes")).toBeVisible();
  await expect(
    caps.getByRole("button", { name: "Install: Not set up" }).first(),
  ).toBeDisabled();
});
