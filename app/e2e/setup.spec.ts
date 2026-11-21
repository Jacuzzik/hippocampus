import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// 7.29: on the very first start, Setup and account opens with the setup checks; never again after that.
test("the first start opens the setup checklist once, with a mark and next step per check", async ({
  page,
}) => {
  await mockSidecar(page, { firstRun: true });
  await page.goto("/");
  const dialog = page.getByRole("dialog", { name: "Setup and account" });
  const list = dialog.getByRole("list", { name: "Setup checks" });
  await expect(list.getByRole("listitem")).toHaveCount(3);
  await expect(dialog.getByText("1 of 3 ready.")).toBeVisible();
  await expect(
    list.getByRole("listitem").filter({ hasText: "Codex program" }),
  ).toContainText("✗");
  await expect(
    list.getByRole("listitem").filter({ hasText: "Backend" }),
  ).toContainText("✓");
  await dialog.getByRole("button", { name: "Check again" }).click();
  await expect(dialog.getByText("1 of 3 ready.")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("Agents").getByText("HIPPO")).toBeVisible();
  await expect(dialog).toHaveCount(0);
});

test("2.09 with no key and no Ollama the main screen says so, with a key button and an Ollama link", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.addInitScript(() => {
    (window as unknown as { __noOllama: boolean }).__noOllama = true;
  });
  await page.goto("/");
  const notice = page.getByLabel("No model set up");
  await expect(notice).toContainText("Ollama is not running");
  await expect(
    notice.getByRole("link", { name: "Install Ollama" }),
  ).toHaveAttribute("href", "https://ollama.com/download");
  await notice.getByRole("button", { name: "Add a key" }).click();
  await expect(page.getByRole("dialog", { name: "Settings" })).toBeVisible();
});

test("2.09 the notice stays away when a model is reachable", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.getByLabel("Agents")).toBeVisible();
  await expect(page.getByLabel("No model set up")).toHaveCount(0);
});
