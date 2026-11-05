import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { canvasDoc, fakeApi, newStudio } from "./fake-api";
import type { FakeStudio } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

type El = { id: string; x: number; y: number; w: number; h: number; name: string; kind: string };
const withCanvas = (): FakeStudio => ({ ...newStudio(), doc: canvasDoc() });
const els = (fake: { studio: FakeStudio }): El[] => (fake.studio.doc?.content.pages[0].elements ?? []) as El[];
const find = (fake: { studio: FakeStudio }, id: string): El => els(fake).find((e) => e.id === id)!;
const saved = (page: Page) => expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });

async function open(page: Page) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  const fake = await fakeApi(page, { studio: withCanvas() });
  await page.goto("/studio");
  await expect(page.locator("[data-el='name']")).toBeVisible();
  return fake;
}

// ------------------------------------------------------------------ the start screen

test("the start screen is three clear steps and starts a resume", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 1000 });
  const fake = await fakeApi(page);
  await page.goto("/studio");
  await expect(page.getByRole("heading", { level: 1, name: "Start your resume" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Where do the words come from/ })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /How do you want to work/ })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Pick a design/ })).toBeVisible();
  // Sensible choices are already made: one click starts.
  await expect(page.getByRole("radio", { name: /My profile/ })).toBeChecked();
  await expect(page.getByRole("radio", { name: /Free design/ })).toBeChecked();
  await page.getByRole("button", { name: "Start my resume" }).click();
  await expect(page.locator("[data-el]").first()).toBeVisible({ timeout: 10_000 });
  expect(fake.studio.doc!.content.version).toBe(2);
});

test("the choices are real radio buttons that work with the arrow keys", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 1000 });
  await fakeApi(page);
  await page.goto("/studio");
  await page.getByRole("radio", { name: /My profile/ }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: /A blank page/ })).toBeChecked();
  await expect(page.getByRole("radio", { name: /A blank page/ })).toBeFocused();
  await page.getByRole("radio", { name: /Guided and ATS-safe/ }).check({ force: true });
  await expect(page.getByRole("heading", { level: 2, name: /Pick a design/ })).toBeVisible();
  await expect(page.getByText("Choose a template").first()).toHaveCount(0);
});

// ------------------------------------------------------------------ the command palette

test("Ctrl K opens the palette, typing narrows it, Enter runs a command and focus comes back", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='headline']").click();
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Commands" });
  await expect(dialog).toBeVisible();
  const box = dialog.getByRole("combobox");
  await expect(box).toBeFocused();
  await box.fill("duplic");
  await expect(dialog.getByRole("option")).toHaveCount(1);
  await expect(dialog.getByRole("option", { name: /Duplicate the selection/ })).toHaveAttribute("aria-selected", "true");
  const before = els(fake).length;
  await page.keyboard.press("Enter");
  await expect(dialog).toBeHidden();
  await saved(page);
  expect(els(fake).length).toBe(before + 1);
});

test("the palette finds commands by words, skips the ones that cannot run, and reaches elements by name", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Commands" }).click();
  const dialog = page.getByRole("dialog", { name: "Commands" });
  // Nothing is selected, so selection commands are not offered.
  await dialog.getByRole("combobox").fill("duplicate");
  await expect(dialog.getByText("Nothing matches that")).toBeVisible();
  await dialog.getByRole("combobox").fill("photo");
  await expect(dialog.getByRole("option", { name: /Add a picture/ })).toBeVisible();
  await dialog.getByRole("combobox").fill("go to headline");
  await expect(dialog.getByRole("option", { name: /Go to Headline/ })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("textbox", { name: /Text of Headline/ })).toBeVisible();
});

test("the palette moves with the arrow keys and closes with Escape", async ({ page }) => {
  await open(page);
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Commands" });
  const options = dialog.getByRole("option");
  await expect(options.first()).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowDown");
  await expect(options.nth(1)).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowUp");
  await expect(options.first()).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("a command runs: zoom in changes the zoom", async ({ page }) => {
  await open(page);
  const width = async () => (await page.locator("[data-page='0']").boundingBox())!.width;
  const before = await width();
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox", { name: "Search commands" }).fill("zoom in");
  await page.keyboard.press("Enter");
  await expect.poll(width).toBeGreaterThan(before);
});

// ------------------------------------------------------------------ recent changes

test("recent changes lists what was done and goes back to before any of it", async ({ page }) => {
  const fake = await open(page);
  const original = { ...find(fake, "headline") };
  await page.locator("[data-el='headline']").click();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.getByRole("button", { name: "Duplicate" }).click();
  await saved(page);
  await page.getByRole("button", { name: "Recent changes" }).click();
  const dialog = page.getByRole("dialog", { name: "Recent changes" });
  const items = dialog.getByRole("listitem");
  await expect(items.nth(0)).toContainText("Duplicated");
  await expect(items.nth(1)).toContainText("Moved");
  await dialog.getByRole("button", { name: /Go back to here, before: Moved/ }).click();
  await saved(page);
  expect(find(fake, "headline").x).toBeCloseTo(original.x, 1);
  expect(els(fake).length).toBe(canvasDoc().content.pages[0]!.elements.length);
});

test("recent changes is empty before any change", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("button", { name: "Recent changes" })).toBeDisabled();
});

// ------------------------------------------------------------------ calm workspace

test("selecting something does not move the page, and the tools for it float over the page", async ({ page }) => {
  await open(page);
  const before = (await page.locator("[data-page='0']").boundingBox())!;
  await expect(page.getByRole("toolbar", { name: "Selection" })).toHaveCount(0);
  await page.locator("[data-el='headline']").click();
  const context = page.getByLabel("Tools for the selection");
  await expect(context).toBeVisible();
  await expect(context.getByRole("button", { name: "Duplicate" })).toBeVisible();
  const after = (await page.locator("[data-page='0']").boundingBox())!;
  expect(after.y).toBeCloseTo(before.y, 0);
  expect(after.x).toBeCloseTo(before.x, 0);
  await page.keyboard.press("Escape");
  await expect(context).toHaveCount(0);
});

test("focus on the page hides the side panel and brings it back", async ({ page }) => {
  await open(page);
  const toggle = page.getByRole("button", { name: "Focus on the page" });
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  const width = async () => (await page.locator(".cv-viewport").boundingBox())!.width;
  const before = await width();
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".cv-inspector")).toBeHidden();
  expect(await width()).toBeGreaterThan(before);
  await toggle.click();
  await expect(page.locator(".cv-inspector")).toBeVisible();
});

test("every page is labelled", async ({ page }) => {
  await open(page);
  await expect(page.getByText("Page 1 of 1")).toBeVisible();
});

test("leaving with edits that are not saved asks first, and a saved resume does not", async ({ page }) => {
  await open(page);
  await saved(page);
  const asks = () =>
    page.evaluate(() => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    });
  expect(await asks()).toBe(false);
  await page.locator("[data-el='headline']").click();
  await page.keyboard.press("ArrowRight");
  expect(await asks()).toBe(true);
  await saved(page);
  await expect.poll(asks).toBe(false);
});

// ------------------------------------------------------------------ speed

test("typing and dragging stay inside the interaction budget", async ({ page }) => {
  await open(page);
  await page.evaluate(() => {
    const w = window as unknown as { __slow: number[] };
    w.__slow = [];
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) w.__slow.push(entry.duration);
    }).observe({ type: "event", durationThreshold: 16, buffered: true } as PerformanceObserverInit);
  });
  // Drag the headline across the page.
  const head = (await page.locator("[data-el='headline']").boundingBox())!;
  await page.mouse.move(head.x + head.width / 2, head.y + head.height / 2);
  await page.mouse.down();
  for (let step = 1; step <= 40; step += 1) await page.mouse.move(head.x + head.width / 2 + step * 3, head.y + head.height / 2);
  await page.mouse.up();
  // Type into it.
  await page.locator("[data-el='headline']").focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Control+a");
  await page.keyboard.type("Typing speed check for the page editor, forty characters or more", { delay: 5 });
  await page.keyboard.press("Escape");
  const slowest = await page.evaluate(() => Math.max(0, ...(window as unknown as { __slow: number[] }).__slow));
  // 200 ms is the line for a good interaction. Anything over it is a regression to look at.
  expect(slowest).toBeLessThan(200);
});

// ------------------------------------------------------------------ accessibility

for (const scheme of ["light", "dark"] as const) {
  test(`axe: the start screen, the palette, recent changes and focus mode (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.setViewportSize({ width: 1500, height: 1000 });
    await fakeApi(page);
    await page.goto("/studio");
    await expect(page.getByRole("heading", { level: 1, name: "Start your resume" })).toBeVisible();
    await axe(page);

    const fake = await fakeApi(page, { studio: withCanvas() });
    void fake;
    await page.goto("/studio");
    await expect(page.locator("[data-el='name']")).toBeVisible();
    await page.locator("[data-el='headline']").click();
    await axe(page);
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog", { name: "Commands" })).toBeVisible();
    await axe(page);
    await page.keyboard.press("Escape");
    await page.keyboard.press("ArrowRight");
    await page.getByRole("button", { name: "Recent changes" }).click();
    await expect(page.getByRole("dialog", { name: "Recent changes" })).toBeVisible();
    await axe(page);
    await page.getByRole("button", { name: "Done" }).click();
    await page.getByRole("button", { name: "Focus on the page" }).click();
    await axe(page);
  });
}
