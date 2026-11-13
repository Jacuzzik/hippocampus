import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

async function openControl(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Control panel" }).click();
  const dialog = page.getByRole("dialog", { name: "Control panel" });
  await expect(dialog).toBeVisible();
  return dialog;
}

test("a dialog moves into place, using the shared durations", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openControl(page);
  const style = await dialog.evaluate((node) => {
    const css = getComputedStyle(node);
    return { name: css.animationName, time: css.animationDuration };
  });
  expect(style).toEqual({ name: "dialog-in", time: "0.2s" });
});

test("with Motion off nothing animates", async ({ page }) => {
  await mockSidecar(page);
  await page.addInitScript(() =>
    localStorage.setItem(
      "hippocampus.prefs",
      JSON.stringify({ motion: "off", intro: "off" }),
    ),
  );
  await page.goto("/");
  const dialog = await openControl(page);
  expect(
    await dialog.evaluate((node) => getComputedStyle(node).animationName),
  ).toBe("none");
});

test("with the computer set to reduced motion, movement is cut to nothing", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockSidecar(page);
  await page.goto("/");
  const dialog = await openControl(page);
  const seconds = await dialog.evaluate((node) =>
    parseFloat(getComputedStyle(node).animationDuration),
  );
  expect(seconds).toBeLessThan(0.001);
});

test("a row in a list fades in, and not at all with Motion off", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("tab", { name: "skills" }).click();
  const row = page
    .getByRole("region", { name: "Skills" })
    .locator("li")
    .first();
  expect(
    await row.evaluate((node) => getComputedStyle(node).animationName),
  ).toBe("fade-in");
  await page.evaluate(() =>
    localStorage.setItem(
      "hippocampus.prefs",
      JSON.stringify({ motion: "off", intro: "off" }),
    ),
  );
  await page.reload();
  await page.getByRole("tab", { name: "skills" }).click();
  expect(
    await page
      .getByRole("region", { name: "Skills" })
      .locator("li")
      .first()
      .evaluate((node) => getComputedStyle(node).animationName),
  ).toBe("none");
});

test("the content of a tab fades in, and not at all with Motion off", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("tab", { name: "skills" }).click();
  const panel = page.getByRole("tabpanel");
  expect(
    await panel.evaluate((node) => getComputedStyle(node).animationName),
  ).toBe("fade-in");
  await page.evaluate(() =>
    localStorage.setItem(
      "hippocampus.prefs",
      JSON.stringify({ motion: "off", intro: "off" }),
    ),
  );
  await page.reload();
  await page.getByRole("tab", { name: "skills" }).click();
  expect(
    await page
      .getByRole("tabpanel")
      .evaluate((node) => getComputedStyle(node).animationName),
  ).toBe("none");
});
