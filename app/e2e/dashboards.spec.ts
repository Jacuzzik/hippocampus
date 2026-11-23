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
  const view = page.getByRole("region", { name: "Dashboards" });
  // The dashboards are icon buttons; each one is named by its label.
  await expect(view.locator("nav.icons button")).toHaveCount(10);
  const names = await view
    .locator("nav.icons button")
    .evaluateAll((buttons) => buttons.map((b) => b.getAttribute("aria-label")));
  expect(names).toEqual([
    "Graph",
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
  await view.getByRole("button", { name: "Notes", exact: true }).click();
  await expect(board.locator("li", { hasText: "Links" }).first()).toContainText(
    "2",
  );
  await view.getByRole("button", { name: "System", exact: true }).click();
  await expect(board.locator("li", { hasText: "Free disk" })).toContainText(
    "120.5 GB",
  );
  await view
    .getByRole("button", { name: "Agents and spend", exact: true })
    .click();
  await expect(board.locator("li:has(b)", { hasText: "kevin" })).toContainText(
    "3.4k",
  );
  await expect(view.getByText(/^Read at /)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(view).toBeHidden();
});

test("Ctrl+D and the palette open the dashboards", async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.keyboard.press("Control+d");
  const view = page.getByRole("region", { name: "Dashboards" });
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
  const view = page.getByRole("region", { name: "Dashboards" });
  const board = view.getByRole("tabpanel");
  await expect(view.getByRole("button", { name: /locked/ })).toHaveText(
    "Locked",
  );
  await expect(board).toHaveAttribute("inert", "");
  // Locked: the failed dashboard's own button cannot be reached, but Refresh in the header can.
  await view.getByRole("button", { name: "Notes", exact: true }).click();
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
    settings.getByRole("tab", { name: "Dashboards", exact: true }),
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
  const view = page.getByRole("region", { name: "Dashboards" });
  await view.getByRole("button", { name: "GitHub", exact: true }).click();
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
  await view.getByRole("button", { name: "GitHub", exact: true }).click();
  await expect(board.getByLabel("Repository")).toHaveValue("nobody/nothing");
});

test("the calendar shows a week with checks and crosses, adds, marks and removes an event, and shows a month", async ({
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
  const view = page.getByRole("region", { name: "Dashboards" });
  await view
    .getByRole("button", { name: "Calendar and scheduling", exact: true })
    .click();
  const board = view.getByRole("tabpanel");
  // The week of the mock's today (Tuesday 17 November): a check, a cross and one the agent is on.
  const tuesday = board.getByRole("group", { name: "2026-11-17", exact: true });
  await expect(
    tuesday.getByRole("button", {
      name: "09:00 Send the weekly report, Completed",
    }),
  ).toBeVisible();
  await expect(
    board.getByRole("button", {
      name: "11:30 Renew the domain, Not completed",
    }),
  ).toBeVisible();
  await expect(
    tuesday.getByRole("button", {
      name: "14:00 Review notes, Agent is on it",
    }),
  ).toBeVisible();
  await expect(
    board.getByRole("group", { name: "All day 2026-11-19" }),
  ).toContainText("Weekly link check");
  const upcoming = board.getByRole("region", { name: "Upcoming" });
  await expect(upcoming).toContainText("Review notes");
  await expect(upcoming).toContainText("Dentist");

  await expect(board.getByRole("button", { name: "Add event" })).toBeDisabled();
  await board.getByLabel("Date").fill("2026-11-19");
  await board.getByLabel("Time").fill("16:00");
  await board.getByLabel("Event", { exact: true }).fill("Pay rent");
  await board.getByRole("button", { name: "Add event" }).click();
  const rent = board.getByRole("button", {
    name: "16:00 Pay rent, Scheduled",
  });
  await expect(rent).toBeVisible();
  await rent.click();
  const details = page.getByRole("dialog", { name: "Pay rent" });
  await details.getByRole("button", { name: "Mark completed" }).click();
  await expect(details).toContainText("Completed");
  await details.getByRole("button", { name: "Remove Pay rent" }).click();
  await expect(details).toHaveCount(0);
  await expect(board.getByText("Pay rent")).toHaveCount(0);

  await board.getByLabel("Event", { exact: true }).fill("boom");
  await board.getByRole("button", { name: "Add event" }).click();
  await expect(board.getByRole("alert")).toContainText(
    "An event needs a title.",
  );

  await board.getByRole("button", { name: "Month" }).click();
  await expect(board.getByText("November 2026")).toBeVisible();
  await expect(board.getByRole("gridcell")).toHaveCount(30);
  await expect(
    board.getByRole("gridcell", { name: "2026-11-20" }),
  ).toContainText("15:30 Dentist");
  await board.getByRole("button", { name: "Next month" }).click();
  await expect(board.getByText("December 2026")).toBeVisible();
  await expect(board.getByRole("gridcell")).toHaveCount(31);
  await board.getByRole("button", { name: "Today" }).click();
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
  const view = page.getByRole("region", { name: "Dashboards" });
  await view.getByRole("button", { name: "Phone", exact: true }).click();
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
  const view = page.getByRole("region", { name: "Dashboards" });
  await expect(
    view.getByRole("button", { name: "Shopify", exact: true }),
  ).toHaveCount(0);
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

  await view.getByRole("button", { name: "Shopify", exact: true }).click();
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
  await expect(
    view.getByRole("button", { name: "Shopify", exact: true }),
  ).toHaveCount(0);
  await expect(
    view.getByRole("button", { name: "Overview", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});

async function box_(
  locator: import("@playwright/test").Locator,
): Promise<{ x: number; y: number; width: number; height: number }> {
  const found = await locator.boundingBox();
  if (!found) throw new Error("The element has no box: it is not on screen.");
  return found;
}

test("a dashboard takes the notes, graph and Control Room space; the bottom bar goes and the agent cards stand on the right", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.locator("footer.status-bar")).toBeVisible();
  await page.keyboard.press("Control+d");
  const view = page.getByRole("region", { name: "Dashboards" });
  for (const name of [
    "Overview",
    "Agents and spend",
    "Tasks",
    "Notes",
    "System",
    "Activity",
    "GitHub",
    "Calendar and scheduling",
    "Phone",
  ]) {
    await view.getByRole("button", { name, exact: true }).click();
    // No bottom bar, no Control Room, no note list, no graph: only the rail, the dashboard and the cards.
    await expect(page.locator("footer.status-bar")).toHaveCount(0);
    await expect(page.locator(".right-panel")).toBeHidden();
    await expect(
      page.getByRole("complementary", { name: "Notes" }),
    ).toBeHidden();
    // The top bar stays; the graph itself is not drawn.
    await expect(page.locator("header.topbar")).toBeVisible();
    await expect(
      page.locator("main.graph > :not(header.topbar)").first(),
    ).toBeHidden();
    const rail = page.getByRole("complementary", { name: "Agent cards" });
    await expect(rail.locator("[data-agent='hippoherman']")).toBeVisible();
    // The agent cards sit left of the dashboard; the dashboard reaches the right and bottom edges.
    const box = await box_(view);
    const railBox = await box_(rail);
    expect(Math.round(box.y + box.height)).toBe(1080);
    expect(Math.round(box.x + box.width)).toBe(1920);
    expect(Math.round(box.x)).toBe(Math.round(railBox.x + railBox.width));
  }
  // The tiles fill the board: the last row ends near the board's bottom.
  await view.getByRole("button", { name: "Overview", exact: true }).click();
  const board = await box_(view.getByRole("tabpanel"));
  const tiles = await box_(view.locator(".tiles"));
  expect(tiles.y + tiles.height).toBeGreaterThan(board.y + board.height - 40);
  // The graph is the main dashboard: choosing it brings the normal layout back.
  await view.getByRole("button", { name: "Graph", exact: true }).click();
  await expect(page.locator("footer.status-bar")).toBeVisible();
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  await expect(
    page.getByRole("complementary", { name: "Agent cards" }),
  ).toHaveCount(0);
});
