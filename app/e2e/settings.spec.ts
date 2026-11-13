import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

async function openSettings(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Control panel" }).click();
  await page
    .getByRole("dialog", { name: "Control panel" })
    .getByRole("button", { name: "Open settings" })
    .click();
  return page.getByRole("dialog", { name: "Settings" });
}

test("settings has a page per category and each one opens", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  const pages: Record<string, string> = {
    General: "Vault folder",
    Appearance: "Terminal text size",
    Agents: "Main agent engine",
    Budgets: "Token budget",
    "Models and keys": "Keys and secrets",
    Connectors: "Checked now",
    Memory: "Memory size per agent",
    "Privacy and data": "Error log",
    Advanced: "Backend (Python sidecar)",
    Doctor: "Doctor",
    Keyboard: "Open the command palette",
    About: "Hippocampus",
  };
  await expect(dialog.getByRole("tab")).toHaveText(Object.keys(pages));
  for (const [name, text] of Object.entries(pages)) {
    await dialog.getByRole("tab", { name, exact: true }).click();
    await expect(
      dialog.getByRole("tabpanel").getByText(text, { exact: true }).first(),
    ).toBeVisible();
  }
});

test("the terminal text size is kept between 10 and 20 and survives a reload", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  let dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Appearance" }).click();
  await dialog.getByRole("button", { name: "Larger terminal text" }).click();
  await expect(dialog.getByText("13px")).toBeVisible();
  for (let i = 0; i < 10; i++) {
    const smaller = dialog.getByRole("button", {
      name: "Smaller terminal text",
    });
    if (await smaller.isDisabled()) break;
    await smaller.click();
  }
  await expect(dialog.getByText("10px")).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Smaller terminal text" }),
  ).toBeDisabled();
  await page.reload();
  dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Appearance" }).click();
  await expect(dialog.getByText("10px")).toBeVisible();
});

test("a connector that is not built yet is a Needs setup card with its reason and what it needs", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Connectors" }).click();
  const slack = dialog.getByRole("article").filter({ hasText: "Slack" });
  await expect(slack).toContainText("Needs setup");
  await expect(slack).toContainText("Needs: A token store");
});

test("searching settings jumps to the matching page", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByLabel("Search settings").fill("slack");
  await expect(dialog.getByRole("tab")).toHaveText(["Connectors"]);
  await expect(
    dialog.getByRole("heading", { name: "Connectors" }),
  ).toBeVisible();
});

test("an error is recorded on disk, listed under Privacy and data, and Clear removes it", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.evaluate(() =>
    window.dispatchEvent(
      new ErrorEvent("error", { error: new Error("boom in a handler") }),
    ),
  );
  await expect(
    page.getByRole("status").filter({ hasText: "1 UI error recorded" }),
  ).toBeVisible();
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Privacy and data" }).click();
  const log = dialog.getByRole("list", { name: "Recorded errors" });
  await expect(log).toContainText("boom in a handler");
  await expect(dialog.getByText("1 recorded")).toBeVisible();
  await dialog.getByRole("button", { name: "Clear" }).click();
  await expect(dialog.getByText("0 recorded")).toBeVisible();
  await expect(log).toHaveCount(0);
});

test("the start-up logo covers the app by default and can be turned off", async ({
  page,
}) => {
  await mockSidecar(page, { intro: true });
  await page.goto("/");
  const logo = page.locator(".loading");
  await expect(logo).toBeVisible();
  await page.evaluate(() =>
    localStorage.setItem("hippocampus.prefs", JSON.stringify({ intro: "off" })),
  );
  await page.reload();
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  await expect(logo).toHaveCount(0);
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Appearance" }).click();
  await expect(dialog.getByRole("tabpanel")).toContainText("Start-up logo");
  await expect(dialog.getByRole("tabpanel")).toContainText("Off");
});

test("Advanced shows the backend log and a switch hides the Connectors page", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Advanced" }).click();
  await expect(dialog.getByLabel("Backend log")).toContainText("Synced vault");
  await expect(dialog.getByRole("tab", { name: "Connectors" })).toBeVisible();
  await dialog.getByRole("checkbox", { name: "Connectors page" }).uncheck();
  await expect(dialog.getByRole("tab", { name: "Connectors" })).toHaveCount(0);
  // The choice is kept for the next start.
  await page.reload();
  const again = await openSettings(page);
  await expect(again.getByRole("tab", { name: "Connectors" })).toHaveCount(0);
});

test("the shell for every agent is a switch that shows the rules in force", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Agents" }).click();
  const rules = dialog.getByRole("list", { name: "Other agents' rules" });
  await expect(rules).toContainText("Shell: not available to this agent.");
  await dialog.getByRole("checkbox", { name: "Shell for every agent" }).check();
  await expect(rules).toContainText("Your program runs in a sandbox.");
});

test("the Doctor page lists each check with what to do about a gap", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Doctor" }).click();
  await expect(
    dialog.getByText("1 fine, 1 to look at, 1 to fix"),
  ).toBeVisible();
  const checks = dialog.getByRole("list", { name: "Checks" });
  await expect(checks.getByRole("listitem")).toHaveCount(3);
  await expect(checks.getByRole("listitem").nth(1)).toContainText("Fix");
  await expect(checks).toContainText("Run `codex login` in a terminal.");
});

test("the Light theme changes the page colours and is kept after a reload", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const root = page.locator("html");
  await expect(root).toHaveAttribute("data-theme", "dark");
  const darkBg = await root.evaluate((el) =>
    getComputedStyle(el).getPropertyValue("--color-bg-0").trim(),
  );
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Appearance" }).click();
  await dialog.getByRole("button", { name: "Theme" }).click();
  await page.getByRole("option", { name: "Light" }).click();
  await expect(root).toHaveAttribute("data-theme", "light");
  const lightBg = await root.evaluate((el) =>
    getComputedStyle(el).getPropertyValue("--color-bg-0").trim(),
  );
  expect(lightBg).not.toBe(darkBg);
  // The graph is drawn again with the new colours, and still shows its notes.
  await expect(page.locator(".brain .labels")).not.toHaveAttribute(
    "data-labels",
    "0",
  );
  await page.reload();
  await expect(root).toHaveAttribute("data-theme", "light");
});

test("settings can be imported as text, and a bad text is refused with the reason", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  const box = dialog.getByLabel("Settings text to import");
  await box.fill("nonsense");
  await dialog.getByRole("button", { name: "Import" }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "This is not a settings file",
  );
  await box.fill('[network]\nmode = "ask"\n');
  await dialog.getByRole("button", { name: "Import" }).click();
  await expect(dialog.getByRole("status")).toContainText("Settings imported");
});

test("Doctor lists broken links and notes with no links", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Doctor" }).click();
  const links = dialog.getByRole("region", { name: "Link doctor" });
  await expect(links).toContainText("3 notes, 1 broken link, 1 with no links");
  await expect(links.getByRole("list", { name: "Broken links" })).toContainText(
    'links to "Missing note"',
  );
  await expect(
    links.getByRole("list", { name: "Notes with no links" }),
  ).toContainText("Gamma.md");
});

test("the command palette opens Settings on the page that was named", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.keyboard.press("Control+p");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await palette.getByRole("combobox").fill("Settings: Doctor");
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await expect(
    dialog.getByRole("heading", { name: "Doctor", exact: true }),
  ).toBeVisible();
});

test("Connectors shows each connector's state and reason from the backend", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openSettings(page);
  await dialog.getByRole("tab", { name: "Connectors" }).click();
  const panel = dialog.getByRole("tabpanel");
  const ollama = panel.locator("article", { hasText: "Local model (Ollama)" });
  await expect(ollama).toContainText("Connected");
  await expect(ollama.getByRole("list", { name: /details/ })).toContainText(
    "llama3.2:3b",
  );
  const github = panel.locator("article", { hasText: "GitHub" });
  await expect(github).toContainText("Not connected");
  await expect(github).toContainText("gh auth login");
  const slack = panel.locator("article", { hasText: "Slack" });
  await expect(slack).toContainText("Needs setup");
  await expect(slack).toContainText("No Slack calls are built yet");
  await expect(panel.getByRole("button", { name: "Test again" })).toBeEnabled();
});

test("a webhook is added and removed in the Control panel Triggers", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("tab", { name: "triggers" }).click();
  await page.getByLabel("Name", { exact: true }).last().fill("Nightly check");
  await page.getByRole("button", { name: "Add webhook" }).click();
  await expect(page.getByText("Nightly check")).toBeVisible();
  await page.getByRole("button", { name: "Remove Nightly check" }).click();
  await page
    .getByRole("button", { name: "Confirm remove Nightly check" })
    .click();
  await expect(page.getByText("Nightly check")).toHaveCount(0);
  await expect(page.getByText("None saved yet.")).toBeVisible();
});
