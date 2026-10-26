import { expect, test, type Page } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// Phone and tablet sizes. Phones span 360 to 430px wide; tablets are portrait and landscape.
const VIEWPORTS = [
  { name: "phone-360", width: 360, height: 740 },
  { name: "phone-390", width: 390, height: 844 },
  { name: "phone-430", width: 430, height: 932 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "tablet-1024", width: 1024, height: 768 },
];

// Touch targets must be at least 44px on touch-sized screens (phones and tablets).
const MIN_TARGET = 44;

// Counts the visible interactive elements smaller than the touch minimum.
async function smallTargets(page: Page): Promise<string[]> {
  return page.$$eval(
    "button, a[href], input, select, textarea, [role='button'], [role='tab'], label:has(input[type='checkbox'])",
    (els, min) =>
      els
        // A checkbox's hit area is its label, so measure the label instead.
        .map((el) =>
          el instanceof HTMLInputElement && el.type === "checkbox"
            ? (el.closest("label") ?? el)
            : el,
        )
        .filter((el) => {
          const r = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          return (
            r.width > 0 &&
            r.height > 0 &&
            style.visibility !== "hidden" &&
            (r.width < min || r.height < min)
          );
        })
        .map(
          (el) =>
            `${el.tagName.toLowerCase()}[${el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 30) ?? ""}] ${Math.round(el.getBoundingClientRect().width)}x${Math.round(el.getBoundingClientRect().height)}`,
        ),
    MIN_TARGET,
  );
}

// True when the page is wider than the window, which means sideways scrolling.
async function sidewaysScroll(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
}

for (const vp of VIEWPORTS) {
  test.describe(`${vp.name} (${vp.width}x${vp.height})`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test.beforeEach(async ({ page }) => {
      await mockSidecar(page);
      await page.goto("/");
      await expect(
        page.getByRole("main", { name: "Brain graph" }),
      ).toBeVisible();
    });

    test("the main screen fits the width with no sideways scroll", async ({
      page,
    }) => {
      expect(await sidewaysScroll(page)).toBe(0);
    });

    test("the main screen touch targets are at least 44px", async ({
      page,
    }) => {
      expect(await smallTargets(page)).toEqual([]);
    });

    test("the command palette fits the width", async ({ page }) => {
      await page.keyboard.press("Control+p");
      await expect(
        page.getByRole("dialog", { name: "Command palette" }),
      ).toBeVisible();
      expect(await sidewaysScroll(page)).toBe(0);
      expect(await smallTargets(page)).toEqual([]);
    });

    // Opens a drawer from the command palette, then checks it sits inside the window.
    for (const [label, selector] of [
      ["Toggle note list", "aside.sidebar"],
      ["Toggle assistant", ".right-panel"],
    ] as const) {
      test(`the "${label}" drawer fits the width`, async ({ page }) => {
        // Wide screens start with both drawers open, so the toggle would close them.
        test.skip(
          vp.width > 900,
          "drawers are open by default on wide screens",
        );
        await page.keyboard.press("Control+p");
        await page.getByText(label, { exact: true }).click();
        const drawer = page.locator(selector).first();
        await expect(drawer).toBeVisible();
        const right = await drawer.evaluate(
          (el) => el.getBoundingClientRect().right,
        );
        expect(right).toBeLessThanOrEqual(vp.width);
        expect(await sidewaysScroll(page)).toBe(0);
        expect(await smallTargets(page)).toEqual([]);
      });
    }

    test("the setup and account dialog fits the width", async ({ page }) => {
      await page
        .getByRole("button", { name: /setup and account/i })
        .first()
        .click();
      await expect(page.getByRole("dialog").first()).toBeVisible();
      expect(await sidewaysScroll(page)).toBe(0);
      expect(await smallTargets(page)).toEqual([]);
    });
  });
}
