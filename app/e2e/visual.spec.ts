import { expect, test, type Page } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// Pixel checks of the main screens, so alignment cannot drift unseen. Baselines live in
// e2e/visual.spec.ts-snapshots and are made on Linux; other systems draw text a little differently, so the
// checks run on Linux only. After an intended change of look: npx playwright test e2e/visual.spec.ts --update-snapshots
test.skip(process.platform !== "linux", "baselines are made on Linux");

const TABS = [
  "terminal",
  "monitor",
  "tasks",
  "inbox",
  "ask me",
  "triggers",
  "history",
  "memory",
  "activity",
  "skills",
  "temps",
];

// Parts that move or depend on the clock are covered, so only layout and colour are compared.
const moving = (page: Page) => [
  page.locator(".brain"),
  page.locator(".xterm"),
  page.locator("time"),
];
const options = (page: Page) => ({
  animations: "disabled" as const,
  caret: "hide" as const,
  mask: moving(page),
  maxDiffPixelRatio: 0.001,
});

async function open(page: Page, theme: "dark" | "light"): Promise<void> {
  await page.addInitScript((chosen) => {
    localStorage.setItem(
      "hippocampus.prefs",
      JSON.stringify({ intro: "off", motion: "off", theme: chosen }),
    );
  }, theme);
  await mockSidecar(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "terminal" })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

for (const theme of ["dark", "light"] as const) {
  test(`the main screen looks the same as its baseline (${theme})`, async ({
    page,
  }) => {
    await open(page, theme);
    await expect(page).toHaveScreenshot(`main-${theme}.png`, options(page));
  });
}

for (const tab of TABS) {
  test(`the ${tab} tab looks the same as its baseline`, async ({ page }) => {
    await open(page, "dark");
    // A tab with waiting items has a count after its name.
    await page.getByRole("tab", { name: new RegExp(`^${tab}`) }).click();
    const panel = page.locator(".right-panel");
    // Wait for the tab's first answer, so the loader is never what gets compared.
    await expect(panel.locator('[aria-busy="true"]:visible')).toHaveCount(0);
    await expect(panel).toHaveScreenshot(
      `tab-${tab.replace(/\W+/g, "-")}.png`,
      options(page),
    );
  });
}

test("Settings, Appearance looks the same as its baseline", async ({
  page,
}) => {
  await open(page, "dark");
  await page.keyboard.press("Control+,");
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await dialog.getByRole("tab", { name: "Appearance" }).click();
  // The dialog covers the moving parts, so nothing is masked here.
  await expect(dialog).toHaveScreenshot("settings-appearance.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixelRatio: 0.001,
  });
});
