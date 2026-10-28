import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
});

test("the sidebar shows the assistant's agent status", async ({ page }) => {
  const agents = page.getByRole("region", { name: "Agent status" });
  await expect(agents.getByText("Assistant")).toBeVisible();
  await expect(
    agents.getByRole("status", { name: "Assistant: Idle" }),
  ).toBeVisible();
});

test("the bottom-right owner panel is present and empty", async ({ page }) => {
  const panel = page.getByRole("region", { name: "Owner panel" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("No cards yet.")).toBeVisible();
});
