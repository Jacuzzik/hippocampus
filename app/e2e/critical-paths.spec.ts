import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the brain graph loads and the orb starts idle", async ({ page }) => {
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  await expect(
    page.getByRole("status", { name: "Assistant: Idle" }).first(),
  ).toBeVisible();
  await expect(page.getByText("Could not load the vault")).toHaveCount(0);
});

test("a question is answered and the tool log shows the read", async ({
  page,
}) => {
  await page
    .getByLabel("Message the assistant")
    .fill("search my notes for alpha");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.getByText("Found Alpha in projects/alpha.md."),
  ).toBeVisible();
  const log = page.getByRole("region", { name: "Tool log" });
  await expect(log.getByText("search_notes")).toBeVisible();
  await expect(log.getByText("done")).toBeVisible();
});

test("a write waits for approval, shows the exact change, then runs", async ({
  page,
}) => {
  await page.getByLabel("Message the assistant").fill("make a new idea note");
  await page.getByRole("button", { name: "Send" }).click();
  const card = page.getByRole("group", { name: "Approval needed" });
  await expect(card).toContainText("+# New idea");
  await expect(
    page.getByRole("status", { name: "Assistant: Waiting for you" }).first(),
  ).toBeVisible();
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Created ideas/new.md.")).toBeVisible();
  await expect(card).toHaveCount(0);
});

test("declining a write leaves the note uncreated", async ({ page }) => {
  await page.getByLabel("Message the assistant").fill("make a new idea note");
  await page.getByRole("button", { name: "Send" }).click();
  await page
    .getByRole("group", { name: "Approval needed" })
    .getByRole("button", { name: "Decline" })
    .click();
  await expect(page.getByText("Okay, I did not create it.")).toBeVisible();
});

test("Stop ends a running chat at once", async ({ page }) => {
  await page.getByLabel("Message the assistant").fill("a long task");
  await page.getByRole("button", { name: "Send" }).click();
  const stop = page.getByRole("button", { name: "Stop" });
  await expect(stop).toBeEnabled();
  const started = Date.now();
  await stop.click();
  await expect(page.getByText("Stopped.")).toBeVisible();
  expect(Date.now() - started).toBeLessThan(1000);
  await expect(
    page.getByRole("status", { name: "Assistant: Idle" }).first(),
  ).toBeVisible();
});

test("Escape is the keyboard stop", async ({ page }) => {
  await page.getByLabel("Message the assistant").fill("a long task");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: "Stop" })).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(page.getByText("Stopped.")).toBeVisible();
});

test("reduced motion turns off the orb pulse", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByLabel("Message the assistant").fill("a long task");
  await page.getByRole("button", { name: "Send" }).click();
  const orb = page.locator(".orb[data-state='thinking']").first();
  await expect(orb).toBeVisible();
  await expect(orb).toHaveCSS("animation-name", "none");
  await page.getByRole("button", { name: "Stop" }).click();
});

test("a note in the list opens in the graph drawer", async ({ page }) => {
  await page
    .getByRole("list", { name: "Note list" })
    .getByRole("button", { name: "Beta" })
    .click();
  await expect(
    page.getByRole("complementary", { name: "Note details" }),
  ).toContainText("beta.md");
});

test("the ribbon hides and shows the note list", async ({ page }) => {
  const toggle = page.getByRole("button", { name: "Note list" });
  await toggle.click();
  await expect(page.getByRole("complementary", { name: "Notes" })).toHaveCount(
    0,
  );
  await toggle.click();
  await expect(
    page.getByRole("complementary", { name: "Notes" }),
  ).toBeVisible();
});

test("the layout fits a 960 by 600 window without scrolling", async ({
  page,
}) => {
  await page.setViewportSize({ width: 960, height: 600 });
  await expect(page.getByRole("main", { name: "Brain graph" })).toBeVisible();
  const fits = await page.evaluate(
    () =>
      document.documentElement.scrollWidth <=
        document.documentElement.clientWidth &&
      document.documentElement.scrollHeight <=
        document.documentElement.clientHeight,
  );
  expect(fits).toBe(true);
});
