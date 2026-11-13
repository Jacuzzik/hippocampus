import { expect, test, type Page } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// Every button on screen must say what it is, and be large enough to hit (24 px, the WCAG 2.2 minimum).
const MIN = 24;

type Problem = { name: string; text: string; width: number; height: number };

async function audit(page: Page): Promise<Problem[]> {
  return page.evaluate((min) => {
    const problems: Problem[] = [];
    for (const button of document.querySelectorAll<HTMLElement>(
      'button, [role="button"], [role="tab"]',
    )) {
      const box = button.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue; // not on screen
      const name = (
        button.getAttribute("aria-label") ??
        button.textContent ??
        button.getAttribute("title") ??
        ""
      ).trim();
      const small = box.width < min || box.height < min;
      if (!name || small)
        problems.push({
          name,
          text: button.outerHTML.slice(0, 120),
          width: Math.round(box.width),
          height: Math.round(box.height),
        });
    }
    return problems;
  }, MIN);
}

test("every button on the main screen has a name and a size that can be hit", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "terminal" })).toBeVisible();
  expect(await audit(page)).toEqual([]);
});

test("every button on each Control Room tab has a name and a size that can be hit", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const tabs = page.getByRole("tablist").first().getByRole("tab");
  const count = await tabs.count();
  expect(count).toBeGreaterThan(5);
  for (let i = 0; i < count; i++) {
    await tabs.nth(i).click();
    expect(await audit(page), await tabs.nth(i).innerText()).toEqual([]);
  }
});

test("every button in the dialogs has a name and a size that can be hit", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Control panel" }).click();
  const control = page.getByRole("dialog", { name: "Control panel" });
  await expect(control).toBeVisible();
  expect(await audit(page), "Control panel").toEqual([]);
  await control.getByRole("button", { name: "Open settings" }).click();
  const settings = page.getByRole("dialog", { name: "Settings" });
  await expect(settings).toBeVisible();
  expect(await audit(page), "Settings").toEqual([]);
  // Every settings page has its own controls.
  const pages = settings.getByRole("tab");
  expect(await pages.count()).toBeGreaterThan(5);
  for (let i = 0; i < (await pages.count()); i++) {
    await pages.nth(i).click();
    expect(await audit(page), await pages.nth(i).innerText()).toEqual([]);
  }
});

test("every button in the Add agent and account dialogs has a name and a size that can be hit", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "+ Add agent" }).first().click();
  await expect(page.getByRole("dialog", { name: "Add agent" })).toBeVisible();
  expect(await audit(page), "Add agent").toEqual([]);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Setup and account" }).click();
  await expect(page.getByRole("dialog").first()).toBeVisible();
  expect(await audit(page), "Setup and account").toEqual([]);
});
