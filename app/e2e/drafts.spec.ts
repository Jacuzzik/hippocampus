import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

test("an unsent message to the assistant is still there after a reload, and gone once cleared", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  const box = page.getByLabel("Message the assistant");
  await box.fill("Remind me to check the link report");
  await page.reload();
  await expect(page.getByLabel("Message the assistant")).toHaveValue(
    "Remind me to check the link report",
  );
  await page.getByLabel("Message the assistant").fill("");
  await page.reload();
  await expect(page.getByLabel("Message the assistant")).toHaveValue("");
  const kept = await page.evaluate(() =>
    Object.keys(localStorage).filter((k) => k.startsWith("hippocampus.draft.")),
  );
  expect(kept).toEqual([]);
});

test("a blocked storage does not stop the message box from working", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new Error("storage is full");
    };
  });
  await mockSidecar(page);
  await page.goto("/");
  const box = page.getByLabel("Message the assistant");
  await box.fill("still typing");
  await expect(box).toHaveValue("still typing");
});
