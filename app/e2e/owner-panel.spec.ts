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
  // 7.04: the lead agent is the orchestrator.
  await expect(info.getByText(/Orchestrator: routes work/)).toBeVisible();
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

test("the Tasks tab can create and edit an owner card", async ({ page }) => {
  await page.getByRole("tab", { name: "tasks" }).click();
  const board = page.getByRole("region", { name: "Tasks" });
  await board.getByRole("textbox", { name: "Card title" }).fill("Reading list");
  await board
    .getByRole("textbox", { name: "Card details" })
    .fill("Read one paper");
  await board.getByRole("button", { name: "Add card" }).click();
  await expect(board.getByText("Reading list")).toBeVisible();
  await board.getByRole("button", { name: "Edit" }).click();
  await board
    .getByRole("textbox", { name: "Edit card title" })
    .fill("Research list");
  await board.getByRole("button", { name: "Save", exact: true }).click();
  await expect(board.getByText("Research list")).toBeVisible();
});

test("a task card starts a temp on its text, and the Temps tab lists it", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "tasks" }).click();
  const board = page.getByRole("region", { name: "Tasks" });
  await board.getByRole("button", { name: "Start a temp on MDF-1" }).click();
  await expect(board.getByRole("status")).toHaveText(
    "Temp started. Its answer shows in the Temps tab.",
  );
  await page.getByRole("tab", { name: "temps" }).click();
  await expect(
    page.getByText(/Work on task MDF-1: Ship the Tasks page/),
  ).toBeVisible();
});

test("a tool call waiting for approval is approved or denied from Ask me", async ({
  page,
}) => {
  await page.evaluate(() => {
    (window as unknown as { __approvals: unknown[] }).__approvals = [
      { call: "t1", name: "delete_note", preview: "Delete ideas/old.md" },
      { call: "t2", name: "write_note", preview: "Write ideas/new.md" },
    ];
  });
  await page.getByRole("tab", { name: "ask me" }).click();
  await expect(
    page.getByText(
      "Codex and Gemini CLI approval prompts appear in their own terminals, not here.",
    ),
  ).toBeVisible();
  const list = page.getByRole("list", { name: "Waiting approvals" });
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await list
    .getByRole("listitem")
    .filter({ hasText: "delete_note" })
    .getByRole("button", { name: "Deny" })
    .click();
  await list
    .getByRole("listitem")
    .filter({ hasText: "write_note" })
    .getByRole("button", { name: "Approve" })
    .click();
  await expect(list).toHaveCount(0);
  expect(
    await page.evaluate(
      () => (window as unknown as { __decided: unknown[] }).__decided,
    ),
  ).toEqual([
    ["t1", false],
    ["t2", true],
  ]);
  const answered = page.getByRole("list", { name: "Answered questions" });
  await expect(answered.getByText("Denied")).toBeVisible();
  await expect(answered.getByText("Approved")).toBeVisible();
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
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const control = page.getByRole("dialog", { name: "Settings" });
  await control.getByRole("tab", { name: "Team and sharing" }).click();
  await control.getByRole("button", { name: "Restore" }).click();
  await expect(bar.getByText("Grace")).toBeVisible();
});

test("a Claude agent's card menu compacts its context by typing /compact into its terminal", async ({
  page,
}) => {
  await page.evaluate(() => {
    (window as unknown as { __cliCommand: string }).__cliCommand =
      "claude --model claude-sonnet-5-5";
  });
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
  // The card learns what its terminal runs on the next poll (every 3 seconds).
  await expect(bar.getByLabel("Context 42").first()).toBeVisible({
    timeout: 10000,
  });
  await bar
    .getByRole("button", { name: "Grace options" })
    .click({ button: "right" });
  await page.getByRole("menuitem", { name: "Resend briefing" }).click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (window as unknown as { __rebriefed?: string[] }).__rebriefed ?? [],
      ),
    )
    .toHaveLength(1);
  await bar
    .getByRole("button", { name: "Grace options" })
    .click({ button: "right" });
  await page.getByRole("menuitem", { name: "Compact context" }).click();
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { __typed?: string[] }).__typed ?? [],
      ),
    )
    .toEqual(expect.arrayContaining(["/compact", "\r"]));
});

test("the card menu's Rename opens the rename box for that agent", async ({
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
  await page.getByRole("menuitem", { name: "Rename" }).click();
  await expect(page.getByRole("dialog").getByRole("textbox")).toHaveValue(
    "Grace",
  );
});

test("Add agent previews the briefing from the words typed so far", async ({
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
  await add.getByRole("button", { name: "Preview briefing" }).click();
  const preview = add.getByLabel("Briefing preview");
  await expect(preview).toContainText("You are Grace,");
  await expect(preview).toContainText("Tidy the notes");
});

test("HIPPO's details say when its briefing was not delivered", async ({
  page,
}) => {
  await page.evaluate(() => {
    (window as unknown as { __delivery: string }).__delivery =
      "Not delivered: the CLI stopped first";
  });
  const bar = page.getByLabel("Agents");
  // The details read the live state, which is read again every 3 seconds.
  await page.waitForTimeout(3500);
  await bar.getByRole("button", { name: "Info", exact: true }).first().click();
  const info = page.getByRole("dialog", { name: "Hippoherman details" });
  await expect(info).toContainText("Not delivered: the CLI stopped first");
  await expect(info).toContainText("Use Resend briefing");
});

test("a card says Crashed with the exit code when its program ended with an error", async ({
  page,
}) => {
  await page.evaluate(() => {
    (window as unknown as { __crashed: number }).__crashed = 3;
  });
  const bar = page.getByLabel("Agents");
  // The card's state is read again every 3 seconds.
  await expect(bar.getByText("Crashed (code 3)").first()).toBeVisible({
    timeout: 10000,
  });
  await bar.getByRole("button", { name: "Info", exact: true }).first().click();
  await expect(
    page.getByRole("dialog", { name: "Hippoherman details" }),
  ).toContainText("Crashed with exit code 3");
});

test("the monitor tab checks the newest CI run of an agent's folder", async ({
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
  await page.getByRole("tab", { name: "monitor" }).click();
  await page.getByRole("button", { name: "Check CI" }).click();
  await expect(page.getByRole("status", { name: "CI status" })).toHaveText(
    "Newest CI run: tests on main: failure.",
  );
});

test("Clear context asks the agent for its handoff first, then clears", async ({
  page,
}) => {
  await page.evaluate(() => {
    (window as unknown as { __cliCommand: string }).__cliCommand =
      "claude --model claude-sonnet-5-5";
  });
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
  await expect(bar.getByLabel("Context 42").first()).toBeVisible({
    timeout: 10000,
  });
  await bar
    .getByRole("button", { name: "Grace options" })
    .click({ button: "right" });
  await page.getByRole("menuitem", { name: "Clear context" }).click();
  const typed = () =>
    page.evaluate(() =>
      ((window as unknown as { __typed?: string[] }).__typed ?? []).filter(
        (t) => t !== "\r",
      ),
    );
  // The clear waits in the queue (3 seconds after the handoff request) and goes in second.
  await expect
    .poll(typed, { timeout: 10000 })
    .toEqual([
      expect.stringMatching(
        /^Write your handoff now: rewrite Grace#\d{4}-Handoff\.md/,
      ),
      "/clear",
    ]);
});

test("a card shows how many times its agent crashed before (7.33)", async ({
  page,
}) => {
  await page.evaluate(async () => {
    const internals = (
      window as unknown as {
        __TAURI_INTERNALS__: {
          invoke: (cmd: string, args: unknown) => Promise<unknown>;
        };
      }
    ).__TAURI_INTERNALS__;
    for (const at of ["2026-11-20T10:00:00Z", "2026-11-21T09:30:00Z"]) {
      await internals.invoke("sidecar_call", {
        method: "record_crash",
        params: {
          at,
          source: "agent hippoherman",
          message: "The CLI stopped with code 1.",
        },
      });
    }
  });
  const strip = page.getByLabel("Agents").getByText("⚠ 2");
  await expect(strip).toBeVisible({ timeout: 10000 });
  await expect(strip).toHaveAttribute(
    "title",
    "2 earlier crashes, last 2026-11-21 09:30",
  );
});

test("the context percentage counts up to its value (12.08)", async ({
  page,
}) => {
  await page.evaluate(() => {
    (window as unknown as { __cliCommand: string }).__cliCommand = "claude";
  });
  await expect(page.getByLabel("Agents").getByText("42%").first()).toBeVisible({
    timeout: 10000,
  });
});

test("the tab underline sits under the chosen tab and moves with it (L.27)", async ({
  page,
}) => {
  const tabs = page.getByRole("tablist", { name: "Panels" });
  const line = tabs.locator(".underline");
  const under = async (name: string) => {
    const tab = await tabs.getByRole("tab", { name }).boundingBox();
    const bar = await line.boundingBox();
    return { tab, bar };
  };
  await tabs.getByRole("tab", { name: "monitor" }).click();
  await expect
    .poll(async () => {
      const { tab, bar } = await under("monitor");
      return tab && bar ? Math.abs(tab.x - bar.x) < 2 : false;
    })
    .toBe(true);
  await tabs.getByRole("tab", { name: "tasks" }).click();
  await expect
    .poll(async () => {
      const { tab, bar } = await under("tasks");
      return tab && bar ? Math.abs(tab.x - bar.x) < 2 : false;
    })
    .toBe(true);
});
