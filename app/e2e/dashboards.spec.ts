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
    "GitHub",
    "Calendar and scheduling",
    "Phone",
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

test("the GitHub dashboard asks for a repository, shows its numbers and says why a read failed", async ({
  page,
}) => {
  await mockSidecar(page);
  // Unlocked for this test, set once so the reload below keeps what the test saved.
  await page.addInitScript(() => {
    if (sessionStorage.getItem("seeded")) return;
    sessionStorage.setItem("seeded", "1");
    localStorage.setItem(
      "hippocampus.prefs",
      JSON.stringify({ intro: "off", dashboardsLocked: false }),
    );
  });
  await page.goto("/");
  await page.keyboard.press("Control+d");
  const view = page.getByRole("dialog", { name: "Dashboards" });
  await view.getByRole("tab", { name: "GitHub" }).click();
  const board = view.getByRole("tabpanel");
  await expect(
    board.getByText(/Write a repository as owner\/name/),
  ).toBeVisible();
  await expect(board.getByRole("button", { name: "Show" })).toBeDisabled();
  await board.getByLabel("Repository").fill("octocat/hello-world");
  await board.getByRole("button", { name: "Show" }).click();
  await expect(
    board.locator("li", { hasText: "Open pull requests" }),
  ).toContainText("2");
  await expect(board.locator("li", { hasText: "Newest CI run" })).toContainText(
    "tests on main.",
  );
  await expect(
    board.locator("li", { hasText: "Pull request #7" }),
  ).toContainText("Add dashboards");
  await board.getByLabel("Repository").fill("nobody/nothing");
  await board.getByRole("button", { name: "Show" }).click();
  await expect(board.getByRole("alert")).toContainText("HTTP 404: Not Found");
  // The repository is kept for the next visit.
  await page.reload();
  await page.keyboard.press("Control+d");
  await view.getByRole("tab", { name: "GitHub" }).click();
  await expect(board.getByLabel("Repository")).toHaveValue("nobody/nothing");
});

test("the calendar shows events and job days, adds and removes an event, and changes month", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.addInitScript(() => {
    if (sessionStorage.getItem("seeded")) return;
    sessionStorage.setItem("seeded", "1");
    localStorage.setItem(
      "hippocampus.prefs",
      JSON.stringify({ intro: "off", dashboardsLocked: false }),
    );
  });
  await page.goto("/");
  await page.keyboard.press("Control+d");
  const view = page.getByRole("dialog", { name: "Dashboards" });
  await view.getByRole("tab", { name: "Calendar and scheduling" }).click();
  const board = view.getByRole("tabpanel");
  await expect(board.getByText("November 2026")).toBeVisible();
  await expect(board.getByRole("gridcell")).toHaveCount(30);
  await expect(
    board.getByRole("gridcell", { name: "2026-11-20" }),
  ).toContainText("15:30 Dentist");
  await expect(
    board.getByRole("gridcell", { name: "2026-11-19" }),
  ).toContainText("Weekly link check");
  await expect(board.getByRole("button", { name: "Add event" })).toBeDisabled();
  await board.getByLabel("Date").fill("2026-11-25");
  await board.getByLabel("Event").fill("Pay rent");
  await board.getByRole("button", { name: "Add event" }).click();
  await expect(
    board.getByRole("gridcell", { name: "2026-11-25" }),
  ).toContainText("Pay rent");
  await board.getByRole("button", { name: "Remove Pay rent" }).click();
  await expect(board.getByText("Pay rent")).toHaveCount(0);
  await board.getByLabel("Event").fill("boom");
  await board.getByRole("button", { name: "Add event" }).click();
  await expect(board.getByRole("alert")).toContainText(
    "An event needs a title.",
  );
  await board.getByRole("button", { name: "Next month" }).click();
  await expect(board.getByText("December 2026")).toBeVisible();
  await expect(board.getByRole("gridcell")).toHaveCount(31);
  await board.getByRole("button", { name: "This month" }).click();
  await expect(board.getByText("November 2026")).toBeVisible();
});

test("the Phone dashboard lists devices and starts and stops mirroring; a phone that has not allowed the computer cannot be mirrored", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.addInitScript(() => {
    if (sessionStorage.getItem("seeded")) return;
    sessionStorage.setItem("seeded", "1");
    localStorage.setItem(
      "hippocampus.prefs",
      JSON.stringify({ intro: "off", dashboardsLocked: false }),
    );
  });
  await page.goto("/");
  await page.keyboard.press("Control+d");
  const view = page.getByRole("dialog", { name: "Dashboards" });
  await view.getByRole("tab", { name: "Phone" }).click();
  const board = view.getByRole("tabpanel");
  const ready = board.locator("li", { hasText: "SM A525F" });
  await expect(ready).toContainText("R58M123ABC · Ready");
  const blocked = board.locator("li", { hasText: "192.168.1.20:5555" });
  await expect(blocked).toContainText("Accept the USB debugging prompt");
  await expect(
    blocked.getByRole("button", { name: "Show here" }),
  ).toBeDisabled();
  // The screen is shown inside the app, below the phone's row.
  await ready.getByRole("button", { name: "Show here" }).click();
  await expect(ready).toContainText("mirroring");
  await expect(
    board.getByRole("img", { name: "Screen of SM A525F" }),
  ).toBeVisible();
  // scrcpy's own window, for taps and keys, can be opened as well.
  await ready.getByRole("button", { name: "Own window" }).click();
  await ready.getByRole("button", { name: "Stop mirroring" }).click();
  await expect(
    board.getByRole("img", { name: "Screen of SM A525F" }),
  ).toHaveCount(0);
  await expect(ready.getByRole("button", { name: "Show here" })).toBeEnabled();
});

test("an app is connected in Settings with a key that is never shown again, gets its own dashboard, and is disconnected", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.keyboard.press("Control+d");
  const view = page.getByRole("dialog", { name: "Dashboards" });
  await expect(view.getByRole("tab", { name: "Shopify" })).toHaveCount(0);
  await view.getByRole("button", { name: /locked/ }).click();
  const settings = page.getByRole("dialog", { name: "Settings" });
  await expect(settings.getByText("0 of 3 connected")).toBeVisible();
  await settings.getByLabel("Find an app").fill("shop");
  await expect(settings.getByRole("button", { name: /^Connect / })).toHaveCount(
    1,
  );
  await settings.getByRole("button", { name: "Connect Shopify" }).click();
  const save = settings.getByRole("button", { name: "Save key" });
  await expect(save).toBeDisabled();
  const key = settings.getByLabel("Key for Shopify");
  await expect(key).toHaveAttribute("type", "password");
  await key.fill("shpat_secret1234");
  await settings.getByLabel("Shop address").fill("evil.com/x");
  await save.click();
  await expect(settings.getByRole("alert")).toContainText("must look like");
  await settings.getByLabel("Shop address").fill("my-shop.myshopify.com");
  await save.click();
  await expect(settings.getByText("Connected · key ends 1234")).toBeVisible();
  await expect(settings.getByText("1 of 3 connected")).toBeVisible();
  // The key reached the backend once and is nowhere on the page.
  expect(
    await page.evaluate(
      () => (window as unknown as { __appKeys: string[] }).__appKeys,
    ),
  ).toEqual(["shpat_secret1234"]);
  expect(await page.content()).not.toContain("shpat_secret1234");
  await settings.getByRole("button", { name: "Close settings" }).click();

  await view.getByRole("tab", { name: "Shopify" }).click();
  const board = view.getByRole("tabpanel");
  await expect(board.locator("li", { hasText: "Orders" })).toContainText("12");
  await expect(board.locator("li", { hasText: "Customers" })).toContainText(
    "Not read",
  );
  await expect(board.locator("li", { hasText: "Customers" })).toContainText(
    "needs read access",
  );

  await view.getByRole("button", { name: /locked/ }).click();
  await settings.getByRole("button", { name: "Disconnect Shopify" }).click();
  await expect(settings.getByText("0 of 3 connected")).toBeVisible();
  await settings.getByRole("button", { name: "Close settings" }).click();
  await expect(view.getByRole("tab", { name: "Shopify" })).toHaveCount(0);
  await expect(view.getByRole("tab", { name: "Overview" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});
