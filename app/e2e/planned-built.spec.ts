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

test("the briefing builder shows each block and its size, and can leave one out (N.04, N.05)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "Agents");
  const blocks = dialog.getByRole("list", { name: "Briefing blocks" });
  await expect(blocks).toContainText("Trail note");
  await expect(dialog.getByText(/5,480 of 16,000 characters/)).toBeVisible();
  await blocks.getByRole("checkbox", { name: "Send Trail note" }).uncheck();
  await expect(dialog.getByText(/5,100 of 16,000 characters/)).toBeVisible();
});

test("Ctrl+Shift+Space keeps a quick thought in the Inbox note (N.17)", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Settings", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Control+Shift+Space");
  const box = page.getByRole("dialog", { name: "Quick capture" });
  await expect(box).toContainText("works while this window is in front");
  await box
    .getByRole("textbox", { name: "Thought" })
    .fill("Call the printer shop");
  await page.keyboard.press("Enter");
  await expect(box).toBeHidden();
  expect(
    await page.evaluate(
      () => (window as unknown as { __captured: string[] }).__captured,
    ),
  ).toEqual(["Call the printer shop"]);
});

test("the first-run tour shows once, and the demo vault opens and closes (N.26)", async ({
  page,
}) => {
  await mockSidecar(page, { firstRun: true });
  await page.goto("/");
  // The setup checklist comes first; the tour waits for it to close.
  await page.keyboard.press("Escape");
  const tour = page.getByRole("dialog", { name: "Tour" });
  await expect(tour).toBeVisible();
  await expect(tour.getByText("Step 1 of 5")).toBeVisible();
  for (let i = 0; i < 4; i++)
    await tour.getByRole("button", { name: "Next" }).click();
  await tour.getByRole("button", { name: "Open the demo vault" }).click();
  await expect(tour).toHaveCount(0);
  await page.reload();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Tour" })).toHaveCount(0);
});

test("Settings opens the demo vault and goes back to the user's vault (N.26)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "General");
  await dialog.getByRole("button", { name: "Open the demo vault" }).click();
  await expect(dialog.getByText("The demo vault is open.")).toBeVisible();
  await dialog.getByRole("button", { name: "Back to my vault" }).click();
  await expect(
    dialog.getByRole("button", { name: "Open the demo vault" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Take the tour" }).click();
  await expect(page.getByRole("dialog", { name: "Tour" })).toBeVisible();
});

test("usage statistics come from the local log and say nothing is sent (7.31)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "Activity");
  await expect(
    dialog.getByText("Nothing is collected, nothing is sent"),
  ).toBeVisible();
  await expect(dialog.getByText("7 events since 2026-11-20")).toBeVisible();
  await expect(
    dialog.getByText("Approvals asked: 2 (1 approved, 1 declined)"),
  ).toBeVisible();
  await expect(
    dialog.getByRole("list", { name: "Most used tools" }),
  ).toContainText("read_note: 4");
  await expect(
    dialog.getByRole("list", { name: "Events per day" }).getByRole("listitem"),
  ).toHaveCount(14);
});

test("the code editor opens a file, saves it, and shows git changes, history and a branch compare (7.18)", async ({
  page,
}) => {
  await mockSidecar(page);
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
  await add.getByRole("button", { name: "claude-sonnet-5-5" }).click();
  await add.getByRole("button", { name: "Next" }).click();
  await add
    .getByRole("textbox", { name: "Goal", exact: true })
    .fill("Tidy the inbox notes");
  await add.getByRole("button", { name: "Spawn" }).click();
  await page.getByLabel("Agents").getByText("Ada").click();
  await page.getByRole("button", { name: "Editor", exact: true }).click();
  const editor = page.getByRole("dialog", { name: "Code editor" });
  await editor.getByRole("button", { name: "src", exact: true }).click();
  await expect(editor.getByRole("button", { name: "util.ts" })).toBeVisible();
  await editor.getByRole("button", { name: "notes.md" }).click();
  const text = editor.locator(".cm-content");
  await expect(text).toContainText("hello");
  await text.click();
  await page.keyboard.press("End");
  await page.keyboard.type(" world");
  await expect(editor.getByRole("tab", { name: /notes\.md ●/ })).toBeVisible();
  await page.keyboard.press("Control+s");
  await expect(editor.getByText("Saved notes.md.")).toBeVisible();
  await expect(editor.getByRole("tab", { name: "notes.md" })).toBeVisible();

  await editor.getByRole("button", { name: "changes", exact: true }).click();
  await editor
    .getByRole("list", { name: "Changed files" })
    .getByRole("button", { name: /notes\.md/ })
    .click();
  await expect(editor.getByLabel("Diff")).toContainText("+hello world");
  await editor.getByRole("button", { name: "history", exact: true }).click();
  await expect(editor.getByRole("list", { name: "Commits" })).toContainText(
    "first commit",
  );
  await editor.getByRole("button", { name: "compare", exact: true }).click();
  await editor.getByRole("button", { name: "Compare branches" }).click();
  await expect(editor.getByText("2 ahead and 1 behind")).toBeVisible();

  await editor.getByRole("button", { name: "search", exact: true }).click();
  await editor.getByRole("textbox", { name: "Find" }).fill("hello");
  await editor.getByRole("button", { name: "Search files" }).click();
  await expect(
    editor.getByRole("list", { name: "Search results" }),
  ).toContainText("notes.md:2");
  await editor.getByRole("textbox", { name: "Replace with" }).fill("hello there");
  await editor.getByRole("button", { name: "Replace in files" }).click();
  await expect(editor.getByText("Updated 1 file.")).toBeVisible();
  await editor.getByRole("button", { name: "changes", exact: true }).click();
  await editor.getByRole("checkbox", { name: "Stage" }).check();
  await editor
    .getByRole("textbox", { name: "Commit message" })
    .fill("Update notes");
  await editor.getByRole("button", { name: "Commit selected files" }).click();
  await expect(editor.getByText("Commit created.")).toBeVisible();
});

test("an agent that asks first shows the exact command or diff, and is approved once, for the folder, or denied (N.12)", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.evaluate(() => {
    const waiting = (
      window as unknown as { __agentWaiting: Record<string, string>[] }
    ).__agentWaiting;
    waiting.push(
      {
        id: "r1",
        agent: "Ada",
        tool: "Bash",
        cwd: "/work/IT",
        command: "npm test --silent",
        file: "",
        diff: "",
        rule: "Run npm commands in /work/IT",
      },
      {
        id: "r2",
        agent: "Ada",
        tool: "Edit",
        cwd: "/work/IT",
        command: "",
        file: "/work/IT/a.txt",
        diff: "--- a/a.txt\n+++ b/a.txt\n-two\n+2\n",
        rule: "Edit files in /work/IT",
      },
    );
  });
  await page.getByRole("tab", { name: "ask me" }).click();
  const list = page.getByRole("list", { name: "Agent approvals" });
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await expect(list.getByLabel("Exact command")).toHaveText(
    "npm test --silent",
  );
  await expect(list.getByLabel("File change")).toContainText("+2");
  await list
    .getByRole("listitem")
    .filter({ hasText: "npm test" })
    .getByRole("button", { name: "Approve for this folder" })
    .click();
  await list
    .getByRole("listitem")
    .filter({ hasText: "a.txt" })
    .getByRole("button", { name: "Deny" })
    .click();
  await expect(list).toHaveCount(0);
  expect(
    await page.evaluate(
      () => (window as unknown as { __agentAnswers: string[] }).__agentAnswers,
    ),
  ).toEqual(["r1:folder", "r2:deny"]);
  const rules = page.getByRole("list", { name: "Folder approvals" });
  await expect(rules).toContainText("Run npm commands in /work/IT");
  await rules.getByRole("button", { name: "Forget" }).click();
  await expect(rules).toHaveCount(0);
});

test("the Slack bot is connected with a pasted token and answers in chosen conversations (7.25)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "Connectors");
  const slack = dialog.getByRole("region", { name: "Slack bot", exact: true });
  await slack.getByLabel("Slack bot token").fill("xoxb-" + "1".repeat(30));
  await slack.getByRole("button", { name: "Connect" }).click();
  await expect(slack.getByText("Connected to Acme as hippo")).toBeVisible();
  await expect(slack.getByLabel("Slack bot token")).toHaveCount(0);
  await slack.getByLabel("#ops").check();
  await slack.getByLabel("Slack bridge").check();
  await expect(slack.getByText("On", { exact: true })).toBeVisible();
  await slack.getByRole("button", { name: "Disconnect" }).click();
  await expect(slack.getByLabel("Slack bot token")).toBeVisible();
});

test("a team is made, saved to and read from, with the code shown to its owner (D.07)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "Team and sharing");
  const teams = dialog.getByRole("region", { name: "Teams", exact: true });
  await teams.getByLabel("Team name").fill("Core team");
  await teams.getByRole("button", { name: "Make a team" }).click();
  await expect(teams.getByRole("list", { name: "Your teams" })).toContainText(
    "Core team",
  );
  await expect(teams.getByText("abcdef012345")).toBeVisible();
  await teams.getByRole("button", { name: "Save to team" }).click();
  await expect(
    teams.getByText("Saved 1 agents, 1 task titles and 1 notes"),
  ).toBeVisible();
  await teams.getByRole("button", { name: "Get from team" }).click();
  await expect(teams.getByText("Got 1 new agents and 1 notes")).toBeVisible();
  await expect(teams.getByRole("list", { name: "Team tasks" })).toContainText(
    "Ship it",
  );
});

test("dictation says what to install, then listens and shows the text (7.27)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "General");
  const dictation = dialog.getByRole("region", {
    name: "Dictation",
    exact: true,
  });
  await expect(dictation.getByText("Not set up yet.")).toBeVisible();
  await expect(
    dictation.getByRole("list", { name: "What to install" }),
  ).toContainText("yay -S whisper.cpp");
  await expect(
    dictation.getByRole("button", { name: "Test: start listening" }),
  ).toBeDisabled();
});

test("Ctrl+Shift+D starts and stops dictation from the window (7.27)", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.keyboard.press("Control+Shift+D");
  await expect(
    page.getByText("Listening. Press Ctrl+Shift+D to finish."),
  ).toBeVisible();
  await page.keyboard.press("Control+Shift+D");
  await expect(
    page.getByText("typed with wtype: hello from the microphone"),
  ).toBeVisible();
});

test("another vault opens in its own window, and a bad folder is refused (7.07)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "General");
  const windows = dialog.getByRole("region", {
    name: "Another vault in a new window",
    exact: true,
  });
  await windows
    .getByLabel("Vault folder for the new window")
    .fill("/home/me/missing");
  await windows.getByRole("button", { name: "Open in a new window" }).click();
  await expect(windows.getByRole("alert")).toContainText("is not a folder");
  await windows
    .getByLabel("Vault folder for the new window")
    .fill("/home/me/work-brain");
  await windows.getByRole("button", { name: "Open in a new window" }).click();
  await expect(
    windows.getByText("work-brain is opening in a new window."),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => (window as unknown as { __windows: string[] }).__windows,
    ),
  ).toEqual(["/home/me/work-brain"]);
});

test("the interface switches to Chinese and to Arabic (right to left), and keeps the choice (7.30)", async ({
  page,
}) => {
  const dialog = await settingsPage(page, "General");
  const html = page.locator("html");
  await expect(html).toHaveAttribute("dir", "ltr");
  await dialog.getByRole("button", { name: "Language", exact: true }).click();
  await dialog.getByRole("option", { name: "简体中文" }).click();
  await expect(html).toHaveAttribute("lang", "zh-Hans");
  await expect(page.getByRole("tab", { name: "外观" })).toBeVisible();
  await expect(page.getByRole("button", { name: "笔记列表" })).toBeVisible();

  await page.getByRole("button", { name: "Language", exact: true }).click();
  await page.getByRole("option", { name: "العربية" }).click();
  await expect(html).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("tab", { name: "المظهر" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "الإعدادات", exact: true }),
  ).toBeVisible();

  // The choice is kept for the next start.
  await page.reload();
  await expect(html).toHaveAttribute("dir", "rtl");
  await expect(
    page.getByRole("button", { name: "قائمة الملاحظات" }),
  ).toBeVisible();
});
