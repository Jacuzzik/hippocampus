import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("the top bar has icons for dashboards, the lock, adding an agent and the palette", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const bar = page.locator("header.topbar");
  for (const name of [
    "Dashboards",
    "Dashboards are locked",
    "Add an agent",
    "Command palette",
    "Full screen layout",
  ])
    await expect(bar.getByRole("button", { name, exact: true })).toBeVisible();
  await bar.getByRole("button", { name: "Add an agent" }).click();
  await expect(page.getByRole("dialog", { name: "Add agent" })).toBeVisible();
  await page.keyboard.press("Escape");
  await bar.getByRole("button", { name: "Command palette" }).click();
  await expect(
    page.getByRole("dialog", { name: "Command palette" }),
  ).toBeVisible();
});

test("dashboards open from the top bar, list six dashboards and show numbers from the backend", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page
    .locator("header.topbar")
    .getByRole("button", { name: "Dashboards", exact: true })
    .click();
  const view = page.getByRole("dialog", { name: "Dashboards" });
  await expect(view.getByRole("tab")).toHaveText([
    "Overview",
    "Agents and spend",
    "Tasks",
    "Notes",
    "System",
    "Activity",
  ]);
  const board = view.getByRole("tabpanel");
  await expect(board.getByText("Tokens today")).toBeVisible();
  await expect(board.locator("li", { hasText: "Tokens today" })).toContainText(
    "15.4k",
  );
  await expect(
    board.locator("li", { hasText: "Questions waiting" }),
  ).toContainText("1");
  await view.getByRole("tab", { name: "Notes" }).click();
  await expect(board.locator("li", { hasText: "Links" }).first()).toContainText(
    "2",
  );
  await view.getByRole("tab", { name: "System" }).click();
  await expect(board.locator("li", { hasText: "Free disk" })).toContainText(
    "120.5 GB",
  );
  await view.getByRole("tab", { name: "Agents and spend" }).click();
  await expect(board.locator("li", { hasText: "kevin" })).toContainText("3.4k");
  await expect(view.getByText(/^Read at /)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(view).toBeHidden();
});

test("Ctrl+D and the palette open the dashboards", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.keyboard.press("Control+d");
  const view = page.getByRole("dialog", { name: "Dashboards" });
  await expect(view).toBeVisible();
  await view.getByRole("button", { name: "Close dashboards" }).click();
  await page.keyboard.press("Control+p");
  await page
    .getByRole("dialog", { name: "Command palette" })
    .getByRole("combobox")
    .fill("dashboards");
  await page.keyboard.press("Enter");
  await expect(view).toBeVisible();
});

test("dashboards are locked by default, and the switch in Settings unlocks them and is kept", async ({
  page,
}) => {
  await mockSidecar(page, { fail: ["graph"] });
  await page.goto("/");
  await page.keyboard.press("Control+d");
  const view = page.getByRole("dialog", { name: "Dashboards" });
  const board = view.getByRole("tabpanel");
  await expect(view.getByRole("button", { name: /locked/ })).toHaveText(
    "Locked",
  );
  await expect(board).toHaveAttribute("inert", "");
  // Locked: the failed dashboard's own button cannot be reached, but Refresh in the header can.
  await view.getByRole("tab", { name: "Notes" }).click();
  await expect(board.getByRole("alert")).toBeVisible();
  await expect(view.getByRole("button", { name: "Refresh" })).toBeEnabled();
  const retry = board.getByRole("button", { name: "Try again" });
  const takesFocus = () =>
    retry.evaluate((node: HTMLElement) => {
      node.focus();
      return document.activeElement === node;
    });
  expect(await takesFocus()).toBe(false);

  await view.getByRole("button", { name: /locked/ }).click();
  const settings = page.getByRole("dialog", { name: "Settings" });
  await expect(
    settings.getByRole("tab", { name: "Dashboards" }),
  ).toHaveAttribute("aria-selected", "true");
  const lock = settings.getByRole("checkbox", { name: "Lock dashboards" });
  await expect(lock).toBeChecked();
  await lock.uncheck();
  await expect(settings.getByText("Dashboards are unlocked.")).toBeVisible();
  await settings.getByRole("button", { name: "Close settings" }).click();
  await expect(view.getByRole("button", { name: /unlocked/ })).toHaveText(
    "Unlocked",
  );
  await expect(board).not.toHaveAttribute("inert", "");
  expect(await takesFocus()).toBe(true);

  await page.reload();
  await expect(
    page
      .locator("header.topbar")
      .getByRole("button", { name: "Dashboards are unlocked" }),
  ).toBeVisible();
});
