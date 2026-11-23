import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("a tab shows its list once loaded, with no loading placeholder left behind", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  for (const tab of [
    "skills",
    "history",
    "memory",
    "tasks",
    "inbox",
    "monitor",
  ]) {
    await page.getByRole("tab", { name: new RegExp(`^${tab}`) }).click();
    await expect(page.getByRole("status", { name: /^Loading / })).toHaveCount(
      0,
    );
  }
});

test("when a list cannot be read, the placeholder gives way to the reason", async ({
  page,
}) => {
  await mockSidecar(page, { fail: ["skills"] });
  await page.goto("/");
  await page.getByRole("tab", { name: "skills" }).click();
  await expect(page.getByText("Could not read the skills.")).toBeVisible();
  await expect(page.getByRole("status", { name: /^Loading / })).toHaveCount(0);
});

test("the start-up screen is a skeleton of the window, with no logo", async ({
  page,
}) => {
  await mockSidecar(page, { intro: true });
  // Hold the first graph load, so start-up stays unfinished and the screen stays up.
  await page.addInitScript(() => {
    const w = window as unknown as {
      __TAURI_INTERNALS__?: {
        invoke: (c: string, a?: { method?: string }) => Promise<unknown>;
        held?: boolean;
      };
    };
    const hold = () => {
      const tauri = w.__TAURI_INTERNALS__;
      if (!tauri || tauri.held) return;
      const real = tauri.invoke;
      tauri.invoke = (c, a) =>
        a?.method === "graph" ? new Promise(() => {}) : real(c, a);
      tauri.held = true;
    };
    hold();
    setInterval(hold, 1);
  });
  await page.goto("/");
  const screen = page.getByRole("status", { name: "Starting Hippocampus" });
  await expect(screen).toBeVisible();
  await expect(screen.locator(".skeleton").first()).toBeVisible();
  await expect(screen).toContainText("Notes and graph");
  await expect(screen.locator("img, .logo")).toHaveCount(0);
});
