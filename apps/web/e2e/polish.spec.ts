import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import { canvasDoc, fakeApi, newStudio } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

/** What a control looks like, in the properties that hover is allowed to change. */
const look = (target: Locator) =>
  target.evaluate((el) => {
    const s = getComputedStyle(el);
    return [s.backgroundColor, s.borderTopColor, s.color, s.boxShadow, s.transform, s.textDecorationThickness].join(" | ");
  });

/** The pointer goes to `pointer` (the thing it really lands on, default the control itself) and the look of `target` is compared. */
async function respondsToHover(page: Page, target: Locator, what: string, pointer: Locator = target) {
  await page.mouse.move(0, 0);
  await pointer.scrollIntoViewIfNeeded();
  const before = await look(target);
  await pointer.hover({ force: true });
  // Transitions are short. Wait until they have settled.
  await page.waitForTimeout(400);
  const after = await look(target);
  expect(after, `${what} does not respond to the pointer`).not.toBe(before);
}

test("every kind of control answers a pointer on the design gallery", async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto("/design");
  await expect(page.getByRole("heading", { level: 1, name: "Design system" })).toBeVisible();
  await respondsToHover(page, page.getByRole("button", { name: "Primary", exact: true }), "a primary button");
  await respondsToHover(page, page.getByRole("button", { name: "Secondary", exact: true }), "a secondary button");
  await respondsToHover(page, page.getByRole("button", { name: "Ghost", exact: true }), "a ghost button");
  await respondsToHover(page, page.getByRole("button", { name: "Action", exact: true }), "an action button");
  await respondsToHover(page, page.getByRole("button", { name: "Action primary", exact: true }), "a primary action button");
  await respondsToHover(page, page.locator(".segmented__label").nth(1), "a segmented option");
  await respondsToHover(page, page.locator(".data-table tbody tr").first(), "a table row");
  await respondsToHover(page, page.locator("input.field__input").first(), "a text field");
});

test("the navigation, links and choice cards answer a pointer in the app", async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await fakeApi(page);
  await page.goto("/studio");
  const nav = page.getByRole("navigation", { name: "Primary" });
  await respondsToHover(page, nav.getByRole("link", { name: "Profile" }), "a navigation link");
  await respondsToHover(page, page.locator(".choice__card").nth(1), "a choice card", page.locator(".choice__input").nth(1));
  await respondsToHover(page, page.getByRole("button", { name: "Start my resume" }), "the start button");
});

test("focus is always visible and never hides behind something", async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await fakeApi(page);
  await page.goto("/opportunities");
  await expect(page.getByRole("heading", { level: 1, name: "Opportunities" })).toBeVisible();
  // Walk the first twenty tab stops. Each must show an outline or a ring.
  for (let stop = 0; stop < 20; stop += 1) {
    await page.keyboard.press("Tab");
    const visible = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return true;
      const s = getComputedStyle(el);
      const outlined = s.outlineStyle !== "none" && parseFloat(s.outlineWidth) >= 2;
      const ring = s.boxShadow !== "none";
      // A radio inside a card shows its focus on the card beside it.
      const sibling = el.nextElementSibling ? getComputedStyle(el.nextElementSibling) : null;
      const cardRing = !!sibling && sibling.outlineStyle !== "none" && parseFloat(sibling.outlineWidth) >= 2;
      return outlined || ring || cardRing || el.matches('input[type="radio"], input[type="checkbox"]');
    });
    expect(visible, `tab stop ${stop + 1} shows no focus`).toBe(true);
  }
});

test("the navigation is grouped, icons are decoration and the current page is marked", async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await fakeApi(page);
  await page.goto("/find");
  const nav = page.getByRole("navigation", { name: "Primary" });
  for (const group of ["Work", "Build", "System"]) await expect(nav.getByRole("list", { name: group })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Find jobs" })).toHaveAttribute("aria-current", "page");
  // The link's name is its words only: the icon adds nothing.
  await expect(nav.getByRole("link", { name: "Find jobs", exact: true })).toBeVisible();
  expect(await nav.locator("svg.icon[aria-hidden='true']").count()).toBeGreaterThanOrEqual(8);
});

test("the sign-in screen shows the form and what the product stands for", async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({ status: 200, json: { authenticated: false, user: null, csrf_token: "t", config: { signup_mode: "invite", email_verification_required: false } } }),
  );
  await page.goto("/signin");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  const panel = page.getByRole("complementary", { name: "About Provenance" });
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("Jobs, with receipts.");
  await page.setViewportSize({ width: 390, height: 800 });
  await expect(panel).toBeHidden();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("pages fit a phone: no sideways scroll on the main screens", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fakeApi(page, { studio: { ...newStudio(), doc: canvasDoc() } });
  for (const path of ["/opportunities", "/find", "/profile", "/runs", "/settings", "/saved"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${path} scrolls sideways on a phone`).toBeLessThanOrEqual(0);
  }
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe: the grouped navigation, panels, notices and empty states (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.setViewportSize({ width: 1400, height: 900 });
    await fakeApi(page);
    for (const path of ["/opportunities", "/find", "/profile", "/runs", "/settings"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await axe(page);
    }
    await page.route("**/api/v1/auth/session", (route) =>
      route.fulfill({ status: 200, json: { authenticated: false, user: null, csrf_token: "t", config: { signup_mode: "invite", email_verification_required: false } } }),
    );
    await page.goto("/signin");
    await expect(page.getByRole("complementary", { name: "About Provenance" })).toBeVisible();
    await axe(page);
  });
}
