import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { canvasDoc, fakeApi, newStudio } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

async function start(page: Page) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  const fake = await fakeApi(page, { studio: newStudio() });
  await page.goto("/studio");
  await expect(page.getByRole("radio", { name: /Ledger/ })).toBeVisible({ timeout: 15_000 });
  return fake;
}

async function begin(page: Page) {
  await page.getByRole("button", { name: "Start my resume" }).click();
  await expect(page.locator("[data-el]").first()).toBeVisible({ timeout: 15_000 });
}

const saved = (page: Page) => expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });
const content = (fake: { studio: { doc: any } }) => fake.studio.doc!.content;

test("the start screen shows the whole library and can filter it by kind of layout", async ({ page }) => {
  await start(page);
  const cards = page.locator(".tpl-card__input");
  await expect(cards).toHaveCount(24);
  await expect(page.getByText("Designed layout").first()).toBeVisible();
  await page.getByRole("radio", { name: "ATS-safe", exact: true }).check();
  const safe = await cards.count();
  expect(safe).toBeGreaterThanOrEqual(10);
  expect(safe).toBeLessThan(24);
  await page.getByRole("radio", { name: "Designed", exact: true }).check();
  expect(await cards.count()).toBe(24 - safe);
});

test("a chosen template is what the resume starts as, with the words filled in", async ({ page }) => {
  const fake = await start(page);
  await page.getByRole("radio", { name: /Banner/ }).check();
  await begin(page);
  const doc = content(fake);
  expect(doc.version).toBe(2);
  expect(doc.style.template).toBe("banner");
  const names = doc.pages[0].elements.map((e: { name: string }) => e.name);
  expect(names).toContain("Header band");
  expect(JSON.stringify(doc)).toContain("Cleaned six CSV sources");
  await expect(page.getByRole("button", { name: "Change template" })).toBeVisible();
});

test("changing the template keeps the words, saves the old layout, and can keep your colors", async ({ page }) => {
  const fake = await start(page);
  await begin(page);
  await page.getByRole("button", { name: "Page and style" }).click();
  await page.locator(".cv-theme", { hasText: "Forest" }).click();
  await saved(page);
  expect(content(fake).style.accent).toBe("#1f5d3a");

  await page.getByRole("button", { name: "Change template" }).click();
  const dialog = page.getByRole("dialog", { name: "Change template" });
  await expect(dialog.getByRole("radio", { name: /Sidebar Left/ })).toBeVisible({ timeout: 15_000 });
  await dialog.getByRole("radio", { name: /Sidebar Left/ }).check();
  await dialog.getByRole("button", { name: "Apply template" }).click();
  await expect(dialog).toBeHidden({ timeout: 15_000 });
  const doc = content(fake);
  expect(doc.style.template).toBe("sidebar-left");
  expect(doc.style.accent).toBe("#1f5d3a"); // kept, because the box was ticked
  expect(JSON.stringify(doc)).toContain("Cleaned six CSV sources");
  expect(fake.studio.saves.at(-1)).toMatchObject({ checkpoint: true });

  await page.getByRole("button", { name: "Change template" }).click();
  await dialog.getByRole("checkbox", { name: "Keep my fonts and colors" }).uncheck();
  await dialog.getByRole("radio", { name: /Dark Sidebar/ }).check();
  await dialog.getByRole("button", { name: "Apply template" }).click();
  await expect(dialog).toBeHidden({ timeout: 15_000 });
  expect(content(fake).style.template).toBe("dark-sidebar");
  expect(content(fake).style.accent).toBe("#2b2f36"); // the graphite that this template starts with
});

test("a color theme sets the accent, text, grey and tint together", async ({ page }) => {
  const fake = await start(page);
  await begin(page);
  await page.getByRole("button", { name: "Page and style" }).click();
  await page.locator(".cv-theme", { hasText: "Burgundy" }).click();
  await saved(page);
  expect(content(fake).style).toMatchObject({ accent: "#7a1f3d", ink: "#231a1d", muted: "#5a4a4f", tint: "#f5ebee" });
  await expect(page.locator(".cv-theme", { hasText: "Burgundy" })).toHaveAttribute("aria-pressed", "true");
  const text = page.getByLabel("Text color", { exact: true });
  await text.fill("#cccccc");
  await expect(page.getByText(/Too light to read on white/)).toBeVisible();
  await text.fill("#112233");
  await saved(page);
  expect(content(fake).style.ink).toBe("#112233");
  await expect(page.locator(".cv-theme", { hasText: "Burgundy" })).toHaveAttribute("aria-pressed", "false");
});

test("the new font pairs can be chosen", async ({ page }) => {
  const fake = await start(page);
  await begin(page);
  await page.getByRole("button", { name: "Page and style" }).click();
  await page.getByLabel("Fonts").selectOption("playfair-source");
  await saved(page);
  expect(content(fake).style.font_pair).toBe("playfair-source");
});

test("a link can be added while editing on the page, and a bad address is refused", async ({ page }) => {
  const fake = await start(page);
  await begin(page);
  await page.locator("[data-el]", { hasText: "Cleaned six CSV" }).first().dblclick();
  const bar = page.getByRole("toolbar", { name: "Formatting for the text being edited" });
  await bar.getByRole("button", { name: "Link" }).click();
  await page.getByLabel("Web address").fill("javascript:alert(1)");
  await page.getByRole("button", { name: "Apply link" }).click();
  await expect(page.getByText(/Use an address like https:\/\/example.com/)).toBeVisible();
  await page.getByLabel("Web address").fill("github.com/asha-rao");
  await page.getByRole("button", { name: "Apply link" }).click();
  await page.keyboard.press("Escape");
  await saved(page);
  expect(JSON.stringify(content(fake))).toContain('"href":"https://github.com/asha-rao"');
});

test("a resume laid out before templates says why it cannot be swapped", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 1000 });
  await fakeApi(page, { studio: { ...newStudio(), doc: canvasDoc() } });
  await page.goto("/studio");
  await page.getByRole("button", { name: "Change template" }).click();
  const dialog = page.getByRole("dialog", { name: "Change template" });
  await expect(dialog.getByText(/laid out before templates existed/)).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Apply template" })).toBeDisabled();
});

for (const theme of ["light", "dark"] as const) {
  test.describe(`axe (${theme})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    });

    test("the gallery, the switcher, the color themes and the link form", async ({ page }) => {
      await start(page);
      await axe(page);
      await begin(page);
      await page.getByRole("button", { name: "Page and style" }).click();
      await axe(page);
      await page.getByRole("button", { name: "Change template" }).click();
      await expect(page.getByRole("dialog").getByRole("radio", { name: /Ledger/ })).toBeVisible({ timeout: 15_000 });
      await axe(page);
      await page.getByRole("button", { name: "Cancel" }).click();
      await page.locator("[data-el]", { hasText: "Cleaned six CSV" }).first().dblclick();
      await page.getByRole("toolbar", { name: "Formatting for the text being edited" }).getByRole("button", { name: "Link" }).click();
      await expect(page.getByLabel("Web address")).toBeVisible();
      await axe(page);
    });
  });
}
