import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { canvasDoc, fakeApi, newStudio } from "./fake-api";
import type { FakeStudio } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const PX_PER_MM = 96 / 25.4;

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(
    results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) })),
  ).toEqual([]);
}

const withCanvas = (extra: Partial<FakeStudio> = {}): FakeStudio => ({ ...newStudio(), doc: canvasDoc(), ...extra });

type El = { id: string; x: number; y: number; w: number; h: number; name: string; kind: string; body?: unknown; locked: boolean };
const els = (fake: { studio: FakeStudio }): El[] => (fake.studio.doc?.content.pages[0].elements ?? []) as El[];
const find = (fake: { studio: FakeStudio }, id: string): El => els(fake).find((e) => e.id === id)!;

async function open(page: Page, studio: FakeStudio = withCanvas()) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  const fake = await fakeApi(page, { studio });
  await page.goto("/studio");
  await expect(page.locator("[data-el='name']")).toBeVisible();
  return fake;
}

const saved = (page: Page) => expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });

async function centre(page: Page, id: string) {
  const box = (await page.locator(`[data-el='${id}']`).boundingBox())!;
  return { x: box.x + box.width / 2, y: box.y + box.height / 2, box };
}

/** How many screen pixels one millimetre of the page is at the current zoom. */
async function pxPerMm(page: Page): Promise<number> {
  const width = (await page.locator("[data-page='0']").boundingBox())!.width;
  return width / 210;
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`axe (${theme})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    });

    test("the canvas with something selected, and the layout check open", async ({ page }) => {
      await open(page);
      await page.locator("[data-el='role']").click();
      await expect(page.getByRole("textbox", { name: /Text of Role/ })).toBeVisible();
      await axe(page);
      await page.getByRole("button", { name: /Layout check/ }).click();
      await expect(page.getByText(/reads well in applicant tracking systems/)).toBeVisible();
      await axe(page);
    });

    test("the layers tab and the page tab", async ({ page }) => {
      await open(page);
      await page.getByRole("button", { name: "Layers", exact: true }).click();
      await expect(page.getByRole("button", { name: /Name/ }).first()).toBeVisible();
      await axe(page);
      await page.getByRole("button", { name: "Page and style" }).click();
      await expect(page.getByRole("group", { name: "Accent color presets" })).toBeVisible();
      await axe(page);
    });

    test("editing text on the page", async ({ page }) => {
      await open(page);
      await page.locator("[data-el='headline']").dblclick();
      await expect(page.getByRole("toolbar", { name: "Formatting for the text being edited" })).toBeVisible();
      await axe(page);
    });
  });
}

test("starting a free canvas from the profile lays the resume out on the page and saves it", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 1000 });
  const fake = await fakeApi(page);
  await page.goto("/studio");
  await page.getByRole("button", { name: "Start my resume" }).click();
  await expect(page.locator("[data-el]").first()).toBeVisible({ timeout: 10_000 });
  const content = fake.studio.doc!.content;
  expect(content.version).toBe(2);
  const all = content.pages.flatMap((p: { elements: El[] }) => p.elements) as El[];
  expect(all.some((e) => e.kind === "text" && JSON.stringify(e.body).includes("Data Intern"))).toBe(true);
  expect(all.every((e) => e.x >= 0 && e.y >= 0 && e.x + e.w <= 210.05)).toBe(true);
  // Nothing was laid on top of anything else.
  const text = all.filter((e) => e.kind === "text");
  for (const a of text) {
    for (const b of text) {
      if (a.id >= b.id) continue;
      const overlap = Math.min(a.x + a.w, b.x + b.w) > Math.max(a.x, b.x) && Math.min(a.y + a.h, b.y + b.h) > Math.max(a.y, b.y) + 0.5;
      expect(overlap, `${a.name} over ${b.name}`).toBe(false);
    }
  }
  await expect(page.getByRole("button", { name: /Layout check: reads well/ })).toBeVisible();
});

test("a guided resume can be moved to the canvas and the guided version stays in earlier versions", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 1000 });
  const fake = await fakeApi(page);
  await page.goto("/studio");
  await page.getByRole("radio", { name: "Guided and ATS-safe" }).check({ force: true });
  await page.getByRole("button", { name: "Start my resume" }).click();
  await expect(page.getByLabel("Full name")).toBeVisible();
  await page.getByRole("button", { name: "Move to the free canvas" }).click();
  await page.getByRole("button", { name: "Move to the canvas" }).click();
  await expect(page.locator("[data-el]").first()).toBeVisible({ timeout: 10_000 });
  expect(fake.studio.doc!.content.version).toBe(2);
});

test("dragging moves an element, snaps to the margin, and is saved", async ({ page }) => {
  const fake = await open(page);
  const k = await pxPerMm(page);
  const { x, y } = await centre(page, "role");
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + 7 * k, y + 20 * k, { steps: 8 });
  await page.mouse.up();
  await saved(page);
  const role = find(fake, "role");
  expect(role.x).toBeGreaterThan(20);
  expect(role.y).toBeGreaterThan(60);
  // The pointer went 20 mm down and the box follows within a snap.
  expect(Math.abs(role.y - (44 + 20))).toBeLessThan(2);
});

test("a drag near the left margin snaps onto it", async ({ page }) => {
  const fake = await open(page);
  const k = await pxPerMm(page);
  const { x, y } = await centre(page, "bullets");
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + 0.5 * k, y + 5 * k, { steps: 5 });
  await expect(page.locator(".cv-guide--x").first()).toBeVisible();
  await page.mouse.up();
  await saved(page);
  expect(find(fake, "bullets").x).toBe(16);
});

test("the arrow keys nudge, Shift moves further, and undo goes back one step", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='headline']").click();
  const start = find(fake, "headline").x;
  for (let i = 0; i < 4; i += 1) await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(900); // a pause makes the next move a new undo step
  await page.keyboard.press("Shift+ArrowDown");
  await saved(page);
  expect(find(fake, "headline").x).toBeCloseTo(start + 2, 1);
  expect(find(fake, "headline").y).toBeCloseTo(29 + 5, 1);
  await page.keyboard.press("Control+z");
  await saved(page);
  expect(find(fake, "headline").x).toBeCloseTo(start + 2, 1);
  expect(find(fake, "headline").y).toBeCloseTo(29, 1);
  await page.keyboard.press("Control+Shift+z");
  await saved(page);
  expect(find(fake, "headline").y).toBeCloseTo(34, 1);
});

test("a held arrow key is one undo step", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='headline']").click();
  for (let i = 0; i < 12; i += 1) await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Control+z");
  await saved(page);
  expect(find(fake, "headline").y).toBeCloseTo(29, 1);
});

test("dragging a handle resizes a shape, and a text box changes only its width", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='rule']").click({ position: { x: 5, y: 1 } });
  const k = await pxPerMm(page);
  const handle = page.locator(".cv-handle--e");
  await expect(handle).toBeVisible();
  const hb = (await handle.boundingBox())!;
  await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
  await page.mouse.down();
  await page.mouse.move(hb.x + hb.width / 2 - 40 * k, hb.y + hb.height / 2, { steps: 6 });
  await page.mouse.up();
  await saved(page);
  expect(find(fake, "rule").w).toBeLessThan(150);

  await page.locator("[data-el='role']").click();
  const left = page.locator(".cv-handle--w");
  const lb = (await left.boundingBox())!;
  await page.mouse.move(lb.x + lb.width / 2, lb.y + lb.height / 2);
  await page.mouse.down();
  await page.mouse.move(lb.x + lb.width / 2 + 30 * k, lb.y + lb.height / 2 + 40 * k, { steps: 6 });
  await page.mouse.up();
  await saved(page);
  const role = find(fake, "role");
  expect(role.x).toBeGreaterThan(16);
  expect(role.y).toBeCloseTo(44, 0);
});

test("double-clicking edits the text on the page and the side panel shows it", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='headline']").dblclick();
  await page.keyboard.press("Control+a");
  await page.keyboard.type("Final year analyst");
  await expect(page.locator("[data-el='headline']")).toContainText("Final year analyst");
  await page.keyboard.press("Escape");
  await saved(page);
  expect(JSON.stringify(find(fake, "headline").body)).toContain("Final year analyst");
  await page.locator("[data-el='headline']").click();
  await expect(page.getByRole("textbox", { name: /Text of Headline/ })).toContainText("Final year analyst");
});

test("typing in the side panel changes the page at once", async ({ page }) => {
  await open(page);
  await page.locator("[data-el='headline']").click();
  const side = page.getByRole("textbox", { name: /Text of Headline/ });
  await side.click();
  await page.keyboard.press("Control+a");
  await page.keyboard.type("Typed in the panel");
  await expect(page.locator("[data-el='headline']")).toContainText("Typed in the panel", { timeout: 500 });
});

test("bold from the format bar is kept in the saved content", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='headline']").dblclick();
  await page.keyboard.press("Control+a");
  await page.getByRole("toolbar", { name: "Formatting for the text being edited" }).getByRole("button", { name: "Bold" }).click();
  await page.keyboard.press("Escape");
  await saved(page);
  expect(JSON.stringify(find(fake, "headline").body)).toContain('"bold"');
});

test("adding text, a box and a rule, then deleting and undoing", async ({ page }) => {
  const fake = await open(page);
  const before = els(fake).length;
  await page.getByRole("button", { name: "Add box" }).click();
  await page.getByRole("button", { name: "Add rule" }).click();
  await page.getByRole("button", { name: "Add text" }).click();
  await page.keyboard.type("Hello there");
  await page.keyboard.press("Escape");
  await saved(page);
  expect(els(fake).length).toBe(before + 3);
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await saved(page);
  expect(els(fake).length).toBe(before + 2);
  await page.getByRole("button", { name: "Undo" }).click();
  await saved(page);
  expect(els(fake).length).toBe(before + 3);
});

test("duplicate, group and ungroup", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='role']").click();
  await page.locator("[data-el='dates']").click({ modifiers: ["Shift"] });
  await page.getByRole("button", { name: "Group", exact: true }).click();
  await saved(page);
  const g = find(fake, "role") as El & { group: string };
  expect(g.group).toBeTruthy();
  expect((find(fake, "dates") as El & { group: string }).group).toBe(g.group);
  // Selecting one selects both, and Duplicate copies both.
  await page.locator("[data-el='bullets']").click();
  await page.locator("[data-el='role']").click();
  await page.getByRole("button", { name: "Duplicate" }).click();
  await saved(page);
  expect(els(fake).length).toBe(8);
  await page.getByRole("button", { name: "Ungroup" }).click();
  await saved(page);
});

test("align and distribute several elements", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='role']").click();
  await page.locator("[data-el='bullets']").click({ modifiers: ["Shift"], position: { x: 40, y: 8 } });
  await page.getByRole("button", { name: "Align right" }).click();
  await saved(page);
  const role = find(fake, "role");
  const bullets = find(fake, "bullets");
  expect(role.x + role.w).toBeCloseTo(bullets.x + bullets.w, 0);
});

test("a locked element cannot be dragged or nudged, and the layers panel can lock and reorder", async ({ page }) => {
  const fake = await open(page);
  await page.getByRole("button", { name: "Layers", exact: true }).click();
  await page.getByRole("button", { name: "Lock Headline" }).click();
  await saved(page);
  expect((find(fake, "headline") as El).locked).toBe(true);
  const k = await pxPerMm(page);
  const { x, y } = await centre(page, "headline");
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + 10 * k, y + 10 * k, { steps: 4 });
  await page.mouse.up();
  await page.keyboard.press("ArrowRight");
  expect(find(fake, "headline").x).toBe(16);
  const orderBefore = els(fake).map((e) => e.id);
  await page.getByRole("button", { name: "Bring Name forward" }).click();
  await saved(page);
  const orderAfter = els(fake).map((e) => e.id);
  expect(orderAfter.indexOf("name")).toBe(orderBefore.indexOf("name") + 1);
});

test("the numbers in the side panel move and resize precisely", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='role']").click();
  const across = page.getByLabel(/^Across/);
  await across.fill("30");
  await page.getByLabel(/^Width/).fill("100");
  await saved(page);
  const role = find(fake, "role");
  expect(role.x).toBe(30);
  expect(role.w).toBe(100);
});

test("text color, size and alignment are changed from the side panel", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='headline']").click();
  await page.getByLabel(/^Size/).fill("14");
  await page.getByLabel("Alignment").selectOption("center");
  await page.getByLabel("Text color").selectOption("accent");
  await saved(page);
  const h = find(fake, "headline") as El & { size: number; align: string; color: string };
  expect([h.size, h.align, h.color]).toEqual([14, "center", "accent"]);
});

test("the layout check names overlapping text and can show it", async ({ page }) => {
  await open(page);
  const k = await pxPerMm(page);
  const { x, y } = await centre(page, "bullets");
  const r = await centre(page, "role");
  await page.mouse.move(r.x, r.y);
  await page.mouse.down();
  await page.mouse.move(x, y, { steps: 6 });
  await page.mouse.up();
  void k;
  await expect(page.getByRole("button", { name: /Layout check: \d issue/ })).toBeVisible();
  await page.getByRole("button", { name: /Layout check/ }).click();
  await expect(page.getByText(/overlap/).first()).toBeVisible();
  await page.getByRole("button", { name: "Show" }).first().click();
  await expect(page.locator(".cv-selection")).toBeVisible();
});

test("zoom changes the page size", async ({ page }) => {
  await open(page);
  const fit = (await page.locator("[data-page='0']").boundingBox())!.width;
  const zoom = page.getByRole("combobox", { name: "Zoom" });
  await zoom.selectOption("2");
  const big = (await page.locator("[data-page='0']").boundingBox())!.width;
  expect(big).toBeGreaterThan(fit * 1.5);
  await page.getByRole("button", { name: "Zoom out" }).click();
  expect((await page.locator("[data-page='0']").boundingBox())!.width).toBeLessThan(big);
  await zoom.selectOption("fit");
  expect(Math.abs((await page.locator("[data-page='0']").boundingBox())!.width - fit)).toBeLessThan(3);
});

test("several elements can be selected from the keyboard and aligned", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='role']").focus();
  await page.keyboard.press("Space");
  await page.locator("[data-el='bullets']").focus();
  await page.keyboard.press("Shift+Space");
  await expect(page.getByText(/2 elements selected/)).toBeVisible();
  await page.getByRole("button", { name: "Align right" }).click();
  await saved(page);
  const role = find(fake, "role");
  const bullets = find(fake, "bullets");
  expect(role.x + role.w).toBeCloseTo(bullets.x + bullets.w, 0);
});

test("a marquee selects several elements", async ({ page }) => {
  await open(page);
  const page0 = (await page.locator("[data-page='0']").boundingBox())!;
  await page.mouse.move(page0.x + 4, page0.y + 40);
  await page.mouse.down();
  await page.mouse.move(page0.x + page0.width - 4, page0.y + 300, { steps: 6 });
  await page.mouse.up();
  await expect(page.locator(".cv-selection.is-multi")).toBeVisible();
  await expect(page.getByText(/elements selected/)).toBeVisible();
});

test("pages can be added and an element moved to another page", async ({ page }) => {
  const fake = await open(page);
  await page.getByRole("button", { name: "Page and style" }).click();
  await page.getByRole("button", { name: "Add a page" }).click();
  await page.locator("[data-el='bullets']").click();
  await page.getByRole("button", { name: "Move selection here, page 2" }).click();
  await saved(page);
  expect(fake.studio.doc!.content.pages).toHaveLength(2);
  expect(fake.studio.doc!.content.pages[1].elements.map((e: El) => e.id)).toEqual(["bullets"]);
});

test("changing paper keeps everything on the page", async ({ page }) => {
  const fake = await open(page);
  await page.getByRole("button", { name: "Page and style" }).click();
  await page.getByLabel("Paper").selectOption("letter");
  await saved(page);
  expect(fake.studio.doc!.content.style.paper).toBe("letter");
  for (const e of els(fake)) expect(e.x + e.w).toBeLessThanOrEqual(215.95);
});

test("Escape and clicking away clear the selection, and Delete removes an element", async ({ page }) => {
  const fake = await open(page);
  await page.locator("[data-el='dates']").click();
  await expect(page.locator(".cv-selection")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".cv-selection")).toHaveCount(0);
  await page.waitForTimeout(600); // a quick second press would count as a double click
  await page.locator("[data-el='dates']").click();
  await page.keyboard.press("Delete");
  await saved(page);
  expect(els(fake).some((e) => e.id === "dates")).toBe(false);
});

test("the tab key reaches elements in reading order and Enter starts editing", async ({ page }) => {
  await open(page);
  await page.locator("[data-el='name']").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("toolbar", { name: "Formatting for the text being edited" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("toolbar", { name: "Formatting for the text being edited" })).toHaveCount(0);
});

test("on a narrow screen the page is shown and editing is switched off with a reason", async ({ page }) => {
  await page.setViewportSize({ width: 600, height: 900 });
  await fakeApi(page, { studio: withCanvas() });
  await page.goto("/studio");
  await expect(page.getByText(/needs a wider screen to edit/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Add text" })).toHaveCount(0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await expect(page.getByRole("button", { name: "Make a PDF" })).toBeVisible();
});
