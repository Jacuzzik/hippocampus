import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test.beforeEach(async ({ page }) => {
  await mockSidecar(page);
  await page.goto("/");
  await page.getByRole("tab", { name: "inbox" }).click();
});

test("messages are grouped into conversations that open to show each message and its state", async ({ page }) => {
  const inbox = page.getByRole("region", { name: "Inbox" });
  await expect(inbox.getByText("1 waiting · 2 conversations")).toBeVisible();
  const thread = inbox.getByRole("button", { name: /Research the plan/ });
  await expect(thread).toContainText("1 waiting");
  await thread.click();
  await expect(inbox.getByText("Read the audit and list the gaps.")).toBeVisible();
  await expect(inbox.getByText("Three gaps found.")).toBeVisible();
  await expect(inbox.getByText("task T-1").first()).toBeVisible();
});

test("a message that was not sent says why", async ({ page }) => {
  const inbox = page.getByRole("region", { name: "Inbox" });
  await inbox.getByRole("button", { name: /Lost message/ }).click();
  await expect(inbox.getByText('Not sent: No agent has the id "zed".')).toBeVisible();
});

test("search narrows the list and an empty result says so", async ({ page }) => {
  const inbox = page.getByRole("region", { name: "Inbox" });
  await inbox.getByRole("searchbox", { name: "Search messages" }).fill("lost");
  await expect(inbox.getByRole("button", { name: /Lost message/ })).toBeVisible();
  await expect(inbox.getByRole("button", { name: /Research the plan/ })).toHaveCount(0);
  await inbox.getByRole("searchbox", { name: "Search messages" }).fill("nothing like this");
  await expect(inbox.getByText("No message matches")).toBeVisible();
});

test("you can write to your agents and the message shows as waiting", async ({ page }) => {
  const inbox = page.getByRole("region", { name: "Inbox" });
  const send = inbox.getByRole("button", { name: "Send message" });
  await expect(send).toBeDisabled();
  await inbox.getByRole("textbox", { name: "Subject" }).fill("Stand-up");
  await inbox.getByRole("textbox", { name: "Message text" }).fill("Report what you are doing.");
  await send.click();
  await expect(inbox.getByRole("status")).toHaveText("Message queued.");
  await expect(inbox.getByRole("button", { name: /Stand-up/ })).toContainText("1 waiting");
  await expect(page.getByRole("tab", { name: "inbox" })).toContainText("2", { timeout: 15000 });
});
