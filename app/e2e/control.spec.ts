import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

async function openControl(
  page: import("@playwright/test").Page,
): Promise<void> {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
}

test("the work pages open from Settings and each lists its panels", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  const tabs: Record<string, string[]> = {
    Work: ["Dispatch", "Scheduled notes jobs", "Triggers"],
    Questions: ["Ask me"],
    "Helpers and skills": ["Helper jobs", "Capabilities", "Skills"],
    "Team and sharing": ["Sharing"],
    Activity: ["Activity log"],
  };
  for (const [name, headings] of Object.entries(tabs)) {
    await dialog.getByRole("tab", { name, exact: true }).click();
    for (const heading of headings) {
      // Some headings carry a status badge, so match the start of the name.
      await expect(
        dialog.getByRole("heading", { name: new RegExp(`^${heading}`) }),
      ).toBeVisible();
    }
  }
});

test("there is no separate control panel: the ribbon has one Settings button", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Control panel" })).toHaveCount(
    0,
  );
  await page.keyboard.press("Control+p");
  await page
    .getByRole("dialog", { name: "Command palette" })
    .getByRole("combobox")
    .fill("dispatch");
  await page.keyboard.press("Enter");
  await expect(
    page
      .getByRole("dialog", { name: "Settings" })
      .getByRole("tab", { name: "Work", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
});

test("network starts Off and a chosen mode is kept", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Agents", exact: true }).click();
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
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Activity", exact: true }).click();
  await dialog.getByRole("button", { name: "Approvals" }).click();
  await expect(
    dialog.getByText("approved by you on the approval card"),
  ).toBeVisible();
  await expect(dialog.getByText("network is Off")).toHaveCount(0);
});

test("sharing is a Planned card and a helper cannot be started empty", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Helpers and skills" }).click();
  await expect(
    dialog.getByRole("button", { name: "Start helper" }),
  ).toBeDisabled();
  await dialog.getByRole("tab", { name: "Team and sharing" }).click();
  const share = dialog.locator("article", {
    hasText: "Share a note by password link",
  });
  await expect(share.getByText("Needs setup", { exact: true })).toBeVisible();
  await expect(
    share.getByText(/Sign in under General > Account/),
  ).toBeVisible();
  // No form that can only fail.
  await expect(dialog.getByRole("button", { name: "Make link" })).toHaveCount(
    0,
  );
});

test("the budget has a 5-hour cap next to day, week and month", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Budgets" }).click();
  await expect(dialog.getByLabel("Assistant 5 hours cap")).toHaveValue("20000");
  await expect(dialog.getByLabel("Whole app day cap")).toHaveValue("200000");
});

test("triggers show the network, the job count and that compaction is on", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Work" }).click();
  await expect(dialog.getByText("1 set, 1 on")).toBeVisible();
  await expect(dialog.getByText("Context compaction is on")).toBeVisible();
  await expect(dialog.getByText("None saved yet.")).toBeVisible();
});

test("scheduled jobs show how many are on", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
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
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Work" }).click();
  await dialog.getByRole("button", { name: "Review and send" }).click();
  await expect(dialog.getByRole("alert")).toHaveText("Write the task.");
  await dialog.getByLabel("Task").fill("Tidy the inbox notes");
  await dialog.getByLabel("Output").fill("A list of what moved");
  await dialog.getByRole("button", { name: "Review and send" }).click();
  const card = dialog.getByRole("alertdialog", { name: "Confirm dispatch" });
  await expect(card).toContainText("Tidy the inbox notes");
  // 8.05: the four-part contract is shown before it goes; an empty part says its default.
  await expect(card).toContainText("A list of what moved");
  await expect(card).toContainText("Default: only this task");
  // One order everywhere (4.14): Cancel first, the action last.
  await expect(card.getByRole("button")).toHaveText(["Cancel", "Send"]);
  await card.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog.getByText("Sent to Helper.")).toHaveCount(0);
  await dialog.getByRole("button", { name: "Review and send" }).click();
  await dialog
    .getByRole("alertdialog", { name: "Confirm dispatch" })
    .getByRole("button", { name: "Send" })
    .click();
  await expect(dialog.getByText("Sent to Helper.")).toBeVisible();

  // The assistant gets the task in its inbox, in the same four parts.
  await dialog.getByLabel("Dispatch to").selectOption("hippoherman");
  await dialog.getByLabel("Task").fill("Plan the release");
  await dialog.getByRole("button", { name: "Review and send" }).click();
  await dialog
    .getByRole("alertdialog", { name: "Confirm dispatch" })
    .getByRole("button", { name: "Send" })
    .click();
  await expect(
    dialog.getByText("Sent to Hippoherman (the assistant)."),
  ).toBeVisible();
});

test("Teams, Plugins, Notion and calendars show only under Planned", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  for (const tab of ["Team and sharing", "Helpers and skills", "Work"]) {
    await dialog.getByRole("tab", { name: tab, exact: true }).click();
    await expect(dialog.getByRole("tabpanel")).not.toContainText(
      /Share agents with other people|MCP servers|Plugins|Assistant \(planned\)/,
    );
  }
  await dialog.getByRole("tab", { name: "Planned", exact: true }).click();
  for (const name of ["Teams", "Plugins", "Notion", "Calendars"]) {
    await expect(
      dialog
        .locator("article")
        .filter({ has: page.getByText(name, { exact: true }) }),
    ).toBeVisible();
  }
});

test("capabilities list the skills and no unbuilt feature card", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Helpers and skills" }).click();
  const caps = dialog.locator("#control-capabilities").locator("..");
  await expect(caps.getByText("tidy-notes")).toBeVisible();
  await expect(caps.locator("article")).toHaveCount(0);
  await expect(caps.getByRole("button", { name: /Not set up/ })).toHaveCount(0);
});

test("a saved webhook can be tested once and the result is shown", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Work" }).click();
  await dialog.getByRole("textbox", { name: "Name" }).fill("Nightly links");
  await dialog.getByRole("button", { name: "Add webhook" }).click();
  await dialog.getByRole("button", { name: "Test Nightly links" }).click();
  await expect(dialog.getByRole("status")).toContainText(
    "Link check: 3 links checked, all working.",
  );
});

test("local model servers show whether each answers, and can be checked again", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Models and keys" }).click();
  const list = dialog.getByRole("list", { name: "Local model servers" });
  await expect(list.getByRole("listitem").nth(0)).toContainText("Answering");
  await expect(list.getByRole("listitem").nth(1)).toContainText("Not running");
  await dialog.getByRole("button", { name: "Test servers" }).click();
  await expect(list.getByRole("listitem").nth(0)).toContainText("Answering");
});

test("a section whose answer fails shows the reason and a Try again button", async ({
  page,
}) => {
  await mockSidecar(page, { fail: ["webhooks"] });
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Work" }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "webhooks is set to fail",
  );
  await expect(dialog.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("the budget lists the tokens each agent used today", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Budgets" }).click();
  const list = dialog.getByRole("list", { name: "Tokens used today by agent" });
  await expect(list.getByRole("listitem")).toHaveText([
    "assistant: 12,000 tokens",
    "kevin: 3,400 tokens",
  ]);
});

test("a scheduled job can be run now and shows its result and new last-run time", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await openControl(page);
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Work" }).click();
  const list = dialog.getByRole("list", { name: "Scheduled jobs" });
  await expect(list).toContainText("last 2026-10-26 07:00");
  await list.getByRole("button", { name: /^Run .* now$/ }).click();
  await expect(list.getByRole("status")).toContainText(
    "3 links checked, all working.",
  );
  await expect(list).toContainText("last 2026-11-15 09:00");
});

test("a custom command agent saves its command and autonomy (7.02, 7.20)", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page
    .getByLabel("Agents")
    .getByRole("button", { name: "+ Add agent" })
    .click();
  const add = page.getByRole("dialog", { name: "Add agent" });
  await add.getByRole("textbox", { name: "Name", exact: true }).fill("Aida");
  await add.getByRole("button", { name: "Next" }).click();
  await add.getByLabel("Folder in workspaces").selectOption("IT");
  await add.getByRole("button", { name: "Next" }).click();
  await add.getByRole("button", { name: "Provider" }).click();
  await add.getByRole("option", { name: "Custom command" }).click();
  await expect(
    add.getByText(/Runs your command inside the sandbox/),
  ).toBeVisible();
  await add.getByRole("button", { name: "Next" }).click();
  await expect(add.getByRole("alert")).toHaveText("Type the command to run.");
  await add.getByRole("textbox", { name: "Command" }).fill("aider --yes");
  await expect(add.locator("code")).toHaveText("aider --yes");
  // "Edit freely" is the default; pick the loosest level.
  const levels = add.getByRole("radiogroup", { name: "Autonomy" });
  await expect(
    levels.getByRole("radio", { name: "Edit freely" }),
  ).toHaveAttribute("aria-checked", "true");
  await levels.getByRole("radio", { name: "Act without asking" }).click();
  await add.getByRole("button", { name: "Next" }).click();
  await add.getByRole("textbox", { name: "Goal", exact: true }).fill("Code");
  await add.getByRole("button", { name: "Spawn" }).click();
  const saved = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("hippocampus.addedAgents") ?? "[]"),
  );
  const aida = saved.find((a: { name: string }) => a.name === "Aida");
  expect(aida).toMatchObject({
    provider: "custom",
    command: "aider --yes",
    autonomy: "full",
  });
});
