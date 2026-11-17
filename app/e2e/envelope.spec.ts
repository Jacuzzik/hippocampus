import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// N.03, 12.10: a delivered hive message flies an envelope from the sender's card to the receiver's.
const seed = () => {
  localStorage.setItem(
    "hippocampus.addedAgents",
    JSON.stringify([{ id: "Ada#1234", name: "Ada", provider: "claude" }]),
  );
};
const deliver = (page: import("@playwright/test").Page) =>
  page.evaluate(() =>
    (
      window as unknown as { __sidecarEvent: (p: unknown) => void }
    ).__sidecarEvent({
      event: "message_sent",
      from: "hippoherman",
      to: "Ada#1234",
    }),
  );

test("a delivered message flies an envelope between the two agent cards", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.addInitScript(seed);
  await page.goto("/");
  const bar = page.getByLabel("Agents");
  await expect(bar.getByText("Ada")).toBeVisible();
  await deliver(page);
  await expect(bar).toHaveAttribute("data-messages-sent", "1");
  await expect(page.locator(".envelope")).toHaveCount(1);
  // It is removed when its flight ends.
  await expect(page.locator(".envelope")).toHaveCount(0);
});

test("no envelope flies when the computer asks for reduced motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockSidecar(page);
  await page.addInitScript(seed);
  await page.goto("/");
  const bar = page.getByLabel("Agents");
  await expect(bar.getByText("Ada")).toBeVisible();
  await deliver(page);
  await expect(bar).toHaveAttribute("data-messages-sent", "1");
  await expect(page.locator(".envelope")).toHaveCount(0);
});
