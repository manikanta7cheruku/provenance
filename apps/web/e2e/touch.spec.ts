import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { CDPSession, Page } from "@playwright/test";
import { canvasDoc, fakeApi, newStudio } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

test.use({ hasTouch: true, isMobile: true, viewport: { width: 390, height: 844 } });

type El = { id: string; x: number; y: number; w: number; h: number };
const withCanvas = () => ({ ...newStudio(), doc: canvasDoc() });

async function open(page: Page) {
  const fake = await fakeApi(page, { studio: withCanvas() });
  await page.goto("/studio");
  await expect(page.locator("[data-el='name']")).toBeVisible();
  return fake;
}

async function cdp(page: Page): Promise<CDPSession> {
  return page.context().newCDPSession(page);
}

type Point = { x: number; y: number; id: number };
const touch = (session: CDPSession, type: "touchStart" | "touchMove" | "touchEnd",  points: Point[]) =>
  session.send("Input.dispatchTouchEvent", { type, touchPoints: points.map((p) => ({ x: p.x, y: p.y, id: p.id })) });

async function centre(page: Page, id: string) {
  const box = (await page.locator(`[data-el='${id}']`).boundingBox())!;
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

test("a phone gets the editor, not a notice", async ({ page }) => {
  await open(page);
  await expect(page.getByText(/needs a wider screen/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add text" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("a tap selects and shows the touch controls, and Edit text starts editing", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("toolbar", { name: "Selected element" })).toHaveCount(0);
  const p = await centre(page, "name");
  await page.touchscreen.tap(p.x, p.y);
  const bar = page.getByRole("toolbar", { name: "Selected element" });
  await expect(bar).toBeVisible();
  await bar.getByRole("button", { name: "Edit text" }).click();
  await expect(page.getByRole("toolbar", { name: "Formatting for the text being edited" })).toBeVisible();
});

test("the buttons move, duplicate and delete without a keyboard", async ({ page }) => {
  const fake = await open(page);
  const p = await centre(page, "name");
  await page.touchscreen.tap(p.x, p.y);
  const bar = page.getByRole("toolbar", { name: "Selected element" });
  const x0 = (fake.studio.doc!.content.pages[0].elements as El[]).find((e) => e.id === "name")!.x;
  await bar.getByRole("button", { name: "Move right" }).click();
  await expect.poll(() => (fake.studio.doc!.content.pages[0].elements as El[]).find((e) => e.id === "name")!.x, { timeout: 8000 }).toBeCloseTo(x0 + 1, 1);
  const count = (fake.studio.doc!.content.pages[0].elements as El[]).length;
  await bar.getByRole("button", { name: "Duplicate" }).click();
  await expect.poll(() => (fake.studio.doc!.content.pages[0].elements as El[]).length, { timeout: 8000 }).toBe(count + 1);
  await bar.getByRole("button", { name: "Delete" }).click();
  await expect.poll(() => (fake.studio.doc!.content.pages[0].elements as El[]).length, { timeout: 8000 }).toBe(count);
});

test("dragging an element with a finger moves it", async ({ page }) => {
  const fake = await open(page);
  const session = await cdp(page);
  const p = await centre(page, "name");
  const x0 = (fake.studio.doc!.content.pages[0].elements as El[]).find((e) => e.id === "name")!.x;
  await touch(session, "touchStart", [{ x: p.x, y: p.y, id: 1 }]);
  for (let i = 1; i <= 6; i++) await touch(session, "touchMove", [{ x: p.x + i * 8, y: p.y, id: 1 }]);
  await touch(session, "touchEnd", []);
  await expect.poll(() => (fake.studio.doc!.content.pages[0].elements as El[]).find((e) => e.id === "name")!.x, { timeout: 8000 }).toBeGreaterThan(x0 + 3);
});

test("two fingers zoom the page and move nothing", async ({ page }) => {
  const fake = await open(page);
  const session = await cdp(page);
  const before = JSON.stringify(fake.studio.doc!.content);
  const width = async () => (await page.locator("[data-page='0']").boundingBox())!.width;
  const w0 = await width();
  const cx = 195;
  const cy = 650;
  await touch(session, "touchStart", [
    { x: cx - 30, y: cy, id: 1 },
    { x: cx + 30, y: cy, id: 2 },
  ]);
  for (let i = 1; i <= 6; i++) {
    await touch(session, "touchMove", [
      { x: cx - 30 - i * 10, y: cy, id: 1 },
      { x: cx + 30 + i * 10, y: cy, id: 2 },
    ]);
  }
  await touch(session, "touchEnd", []);
  await expect.poll(width).toBeGreaterThan(w0 * 1.3);
  expect(JSON.stringify(fake.studio.doc!.content)).toBe(before);
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe on a phone with something selected (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await open(page);
    const p = await centre(page, "name");
    await page.touchscreen.tap(p.x, p.y);
    await expect(page.getByRole("toolbar", { name: "Selected element" })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
  });
}
