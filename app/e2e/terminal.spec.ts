import { expect, test, type Page } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

type Call = { method: string; agent: string; [key: string]: unknown };
const calls = (page: Page): Promise<Call[]> =>
  page.evaluate(
    () => (window as unknown as { __terminalCalls: Call[] }).__terminalCalls,
  );

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the main agent's terminal starts its CLI once", async ({ page }) => {
  await expect(page.getByLabel("Live terminal").locator(".xterm")).toHaveCount(
    1,
  );
  const starts = (await calls(page)).filter(
    (call) => call.method === "terminal_start",
  );
  expect(starts).toHaveLength(1);
  expect(starts[0]).toMatchObject({ agent: "hippoherman", block_tools: false });
});

test("an added agent runs in the same terminal, and block tools restarts it", async ({
  page,
}) => {
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

  const screen = page.getByLabel("Terminal for Ada");
  await expect(screen.locator(".xterm")).toHaveCount(1);
  const own = async (): Promise<Call[]> =>
    (await calls(page)).filter((call) => call.agent !== "hippoherman");
  await expect.poll(async () => (await own()).length).toBe(1);
  expect((await own())[0]).toMatchObject({
    method: "terminal_start",
    model: "claude-sonnet-5-5",
    block_tools: false,
  });
  expect(String((await own())[0].folder)).toContain("IT");

  await page.getByLabel("Agents").getByText("Ada").click();
  // Blocking tools ends the session, so it asks first; Cancel changes nothing.
  await page.getByRole("button", { name: "block tools" }).click();
  await page.getByRole("button", { name: "Cancel" }).click();
  expect((await own()).length).toBe(1);
  await page.getByRole("button", { name: "block tools" }).click();
  await page.getByRole("button", { name: "Restart without tools" }).click();
  await expect
    .poll(async () => (await own()).map((call) => call.method))
    .toEqual(["terminal_start", "terminal_stop", "terminal_start"]);
  expect((await own())[2]).toMatchObject({ block_tools: true });
  // The old screen is gone: one terminal in the box, not two drawn over each other.
  await expect(screen.locator(".xterm")).toHaveCount(1);

  // Traces lists what the agent ran, with the result; Messages lists its own messages.
  await page.getByRole("tab", { name: "Traces" }).click();
  const traces = page.getByRole("list", { name: "Tool calls by Ada" });
  await expect(traces.getByRole("listitem").first()).toContainText("failed");
  await expect(traces).toContainText("rm notes.md");
  await expect(traces).toContainText("read_note");
  await page.getByRole("tab", { name: "Messages" }).click();
  await expect(page.getByText("No messages yet")).toBeVisible();
});

test("TALK on the main agent's card puts the cursor in its message box", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "tasks" }).click();
  await page
    .getByLabel("Agents")
    .getByRole("button", { name: "TALK", exact: true })
    .first()
    .click();
  await expect(page.getByRole("tab", { name: "terminal" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    page.getByRole("textbox", { name: /^Message / }).first(),
  ).toBeFocused();
});

test("after the backend restarts, the agent's program is started again", async ({
  page,
}) => {
  await expect(page.getByLabel("Live terminal").locator(".xterm")).toHaveCount(
    1,
  );
  const starts = async (): Promise<number> =>
    (await calls(page)).filter((call) => call.method === "terminal_start")
      .length;
  await expect.poll(starts).toBe(1);
  // The cards ask for each agent's state every few seconds; a new id in the answer means a restart.
  await page.waitForTimeout(3500);
  expect(await starts()).toBe(1); // the same backend: nothing is started twice
  await page.evaluate(
    () => ((window as unknown as { __boot: string }).__boot = "boot-2"),
  );
  await expect.poll(starts, { timeout: 10000 }).toBe(2);
  await expect(page.getByLabel("Live terminal").locator(".xterm")).toHaveCount(
    1,
  );
});

test("the terminal's state is a live region a screen reader announces", async ({
  page,
}) => {
  const state = page.getByRole("status", { name: "Terminal state" });
  await expect(state).toHaveText(/running|idle/);
  await expect(state).toHaveAttribute("role", "status");
});

test("focus mode dims the notes and the graph around the selected agent, and Escape leaves", async ({
  page,
}) => {
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
  const opacity = () =>
    page
      .locator("main.graph")
      .evaluate((node) => getComputedStyle(node).opacity);
  const focus = async (): Promise<void> => {
    await page.keyboard.press("Control+p");
    await page.getByRole("combobox").fill("Focus on the selected agent");
    await page.keyboard.press("Enter");
  };
  // With no agent selected, the command does nothing.
  await focus();
  expect(await opacity()).toBe("1");
  await page.getByRole("button", { name: "TALK" }).last().click();
  await focus();
  await expect.poll(opacity).toBe("0.3");
  await page.keyboard.press("Escape");
  await expect.poll(opacity).toBe("1");
});
