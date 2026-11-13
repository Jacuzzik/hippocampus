import { expect, test, type Page } from "@playwright/test";
import { mockSidecar } from "./tauri-mock";

// Window-size matrix (3.15) and font check (6.16): every screen is opened at three window sizes. On each one
// nothing makes the page scroll sideways, and every piece of text uses the app's own fonts.
const SIZES = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 960, height: 600 }, // the smallest the window can be (tauri.conf.json minWidth, minHeight)
];

async function problems(page: Page, where: string): Promise<string[]> {
  return page.evaluate((label) => {
    const found: string[] = [];
    const root = document.documentElement;
    if (root.scrollWidth > root.clientWidth + 1)
      found.push(
        `${label}: the page scrolls sideways (${root.scrollWidth} > ${root.clientWidth})`,
      );
    // The fonts the tokens name (--font-ui, --font-mono), plus the terminal's own Nerd Font.
    const style = getComputedStyle(root);
    const allowed = ["--font-ui", "--font-mono"].map((name) =>
      style.getPropertyValue(name).split(",")[0]?.replace(/["']/g, "").trim(),
    );
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
    );
    const seen = new Set<string>();
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const parent = node.parentElement;
      if (!parent || !node.textContent?.trim()) continue;
      if (parent.closest(".xterm, script, style")) continue;
      const box = parent.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      const first =
        getComputedStyle(parent)
          .fontFamily.split(",")[0]
          ?.replace(/["']/g, "")
          .trim() ?? "";
      if (!allowed.includes(first) && !seen.has(first)) {
        seen.add(first);
        found.push(
          `${label}: text in "${first}" (allowed: ${allowed.join(", ")})`,
        );
      }
    }
    return found;
  }, where);
}

for (const size of SIZES) {
  test(`every Control Room tab and Settings page at ${size.width}x${size.height} has no sideways scroll and only the app's fonts`, async ({
    page,
  }) => {
    await page.setViewportSize(size);
    await mockSidecar(page);
    await page.goto("/");
    await expect(page.getByRole("tab", { name: "terminal" })).toBeVisible();
    const found: string[] = [];
    found.push(...(await problems(page, "main screen")));
    for (const tab of await page
      .getByRole("tablist")
      .first()
      .getByRole("tab")
      .all()) {
      const name = (await tab.innerText()).replace(/\s*\d+$/, "").trim();
      await tab.click();
      found.push(...(await problems(page, `tab ${name}`)));
    }
    await page.keyboard.press("Control+p");
    await page.getByRole("combobox").fill("Settings: General");
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Settings" });
    await expect(dialog).toBeVisible();
    for (const tab of await dialog.getByRole("tab").all()) {
      const name = await tab.innerText();
      await tab.click();
      found.push(...(await problems(page, `Settings ${name}`)));
    }
    expect(found).toEqual([]);
  });
}

// E.04: pressing Tab walks the main screen, and every stop shows where the keyboard is.
test("Tab visits every control on the main screen and each one shows a focus mark", async ({
  page,
}) => {
  await mockSidecar(page);
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "terminal" })).toBeVisible();
  const stops: string[] = [];
  const unmarked: string[] = [];
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const css = getComputedStyle(el);
      const outline =
        css.outlineStyle !== "none" && parseFloat(css.outlineWidth) > 0;
      const shadow = css.boxShadow !== "none";
      const name =
        el.getAttribute("aria-label") ??
        el.textContent?.trim().slice(0, 30) ??
        el.tagName;
      // The terminal's own text area and the hidden graph canvas are not controls a person sees.
      const hidden = el.classList.contains("xterm-helper-textarea");
      return {
        name: `${el.tagName.toLowerCase()} ${name}`,
        marked: outline || shadow,
        hidden,
      };
    });
    if (!info) break;
    if (info.hidden) continue;
    if (stops.includes(info.name) && stops.indexOf(info.name) === 0) break; // wrapped around
    stops.push(info.name);
    if (!info.marked) unmarked.push(info.name);
  }
  expect(stops.length).toBeGreaterThan(10);
  expect(unmarked).toEqual([]);
});
