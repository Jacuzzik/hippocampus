import { expect, test } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// N.23: a note is pinned to an agent from its right-click menu; the agent's Pinned tab shows the token cost,
// warns past the limit, and unpins.
test("a note pinned to an agent shows on its Pinned tab with the token cost, and unpins", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.addInitScript(() => {
    if (sessionStorage.getItem("seeded")) return;
    sessionStorage.setItem("seeded", "1");
    localStorage.setItem(
      "hippocampus.addedAgents",
      JSON.stringify([
        {
          id: "Ada#1234",
          name: "Ada",
          provider: "claude",
          pinned: ["beta.md"],
        },
      ]),
    );
  });
  await page.goto("/");
  const graph = page.getByRole("main", { name: "Brain graph" });
  const canvas = graph.locator("canvas.canvas");
  await expect(canvas).toHaveAttribute("data-in-view", "3");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("the graph canvas has no box");
  const style = await graph
    .locator(".label", { hasText: /^Alpha$/ })
    .getAttribute("style");
  const m = /translate\((-?[\d.]+)px, (-?[\d.]+)px\)/.exec(style ?? "");
  if (!m) throw new Error("no label for Alpha");
  // Labels sit 8px right of and 7px above the node (see graph-drag.spec.ts).
  await page.mouse.click(box.x + Number(m[1]) - 8, box.y + Number(m[2]) + 7, {
    button: "right",
  });
  const menu = page.getByRole("menu", { name: "Note actions" });
  await menu.getByRole("menuitem", { name: "Pin to an agent…" }).click();
  const ada = menu.getByRole("menuitemcheckbox", { name: /Ada/ });
  await expect(ada).toHaveAttribute("aria-checked", "false");
  await ada.click();
  await expect(ada).toHaveAttribute("aria-checked", "true");
  // A click outside the menu closes it.
  await page.locator(".menu-scrim").click({ position: { x: 5, y: 5 } });
  await expect(menu).toHaveCount(0);

  await page
    .getByLabel("Agents")
    .getByRole("button", { name: "Ada options" })
    .click();
  await page.getByRole("tab", { name: "Pinned" }).click();
  const list = page.getByRole("list", { name: "Notes pinned to Ada" });
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await expect(
    page.getByText(/About 1800 tokens on every start: more than/),
  ).toBeVisible();
  await list.getByRole("button", { name: "Unpin alpha.md" }).click();
  await expect(list.getByRole("listitem")).toHaveCount(1);
  await expect(
    page.getByText("About 900 tokens on every start."),
  ).toBeVisible();
});
