import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { canvasDoc, fakeApi, newStudio } from "./fake-api";
import type { FakeStudio, FakeTheme } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

const withCanvas = (): FakeStudio => ({ ...newStudio(), doc: canvasDoc() });
const style = (fake: { studio: FakeStudio }) => fake.studio.doc!.content.style as Record<string, string>;

const FOREST: FakeTheme = {
  id: "theme-1",
  name: "Forest look",
  font_pair: "plex-newsreader",
  accent: "#1f5d3a",
  ink: "#1b1f1c",
  muted: "#4a524d",
  tint: "#eaf2ec",
  updated_at: "2026-11-05T10:00:00Z",
};

async function open(page: Page, themes: FakeTheme[] = []) {
  await page.setViewportSize({ width: 1500, height: 1000 });
  const fake = await fakeApi(page, { studio: withCanvas(), themes: themes.map((t) => ({ ...t })) });
  await page.goto("/studio");
  await expect(page.locator("[data-el='name']")).toBeVisible();
  await page.getByRole("button", { name: "Page and style" }).click();
  await expect(page.getByRole("group", { name: "Color themes" })).toBeVisible();
  return fake;
}

const saved = (page: Page) => expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });
const panel = (page: Page) => page.getByRole("group", { name: "My themes" });

test("the panel explains itself and starts empty", async ({ page }) => {
  await open(page);
  await expect(panel(page)).toContainText("never changes your words");
  await expect(panel(page)).toContainText("No saved themes yet");
  await expect(panel(page).getByRole("button", { name: "Save this look" })).toBeDisabled();
});

test("the look of this resume is saved under a name", async ({ page }) => {
  const fake = await open(page);
  await panel(page).getByLabel("Name for this theme").fill("Interview blue");
  await panel(page).getByRole("button", { name: "Save this look" }).click();
  await expect(page.getByText("Saved as Interview blue.").first()).toBeVisible();
  const list = panel(page).getByRole("list", { name: "Saved themes" });
  await expect(list).toContainText("Interview blue");
  expect(fake.themes).toHaveLength(1);
  expect(fake.themes[0]).toMatchObject({ name: "Interview blue", accent: style(fake).accent, tint: style(fake).tint, font_pair: style(fake).font_pair });
});

test("a saved theme is put on the resume and saved with it", async ({ page }) => {
  const fake = await open(page, [FOREST]);
  expect(style(fake).accent).not.toBe(FOREST.accent);
  await page.getByRole("button", { name: "Use Forest look" }).click();
  await saved(page);
  expect(style(fake)).toMatchObject({ accent: FOREST.accent, ink: FOREST.ink, muted: FOREST.muted, tint: FOREST.tint, font_pair: FOREST.font_pair });
  await expect(page.getByRole("button", { name: "Use Forest look" })).toHaveAttribute("aria-pressed", "true");
  await expect(panel(page)).toContainText("in use on this resume");
  await expect(page.getByLabel("Custom color")).toHaveValue(FOREST.accent);
});

test("applying a theme changes the look and none of the words", async ({ page }) => {
  const fake = await open(page, [FOREST]);
  const before = JSON.stringify((fake.studio.doc!.content.pages as { elements: { id: string; body?: unknown }[] }[])[0]!.elements.map((e) => [e.id, e.body]));
  await page.getByRole("button", { name: "Use Forest look" }).click();
  await saved(page);
  const after = JSON.stringify((fake.studio.doc!.content.pages as { elements: { id: string; body?: unknown }[] }[])[0]!.elements.map((e) => [e.id, e.body]));
  expect(after).toBe(before);
});

test("a theme can be updated to the current look, renamed and deleted", async ({ page }) => {
  const fake = await open(page, [FOREST]);
  // Change the resume, then update the theme to match.
  await page.getByRole("button", { name: "Burgundy" }).click();
  await saved(page);
  await page.getByRole("button", { name: "Update Forest look to the look of this resume" }).click();
  await expect(page.getByText("Forest look now has the look of this resume.").first()).toBeVisible();
  expect(fake.themes[0]!.accent).toBe(style(fake).accent);

  await page.getByRole("button", { name: "Rename Forest look" }).click();
  await page.getByLabel("New name for Forest look").fill("Burgundy look");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect(panel(page).getByText("Burgundy look")).toBeVisible();
  expect(fake.themes[0]!.name).toBe("Burgundy look");

  await page.getByRole("button", { name: "Delete Burgundy look" }).click();
  expect(fake.themes).toHaveLength(1);
  await page.getByRole("button", { name: "Delete it, Burgundy look" }).click();
  await expect(panel(page)).toContainText("No saved themes yet");
  expect(fake.themes).toHaveLength(0);
  expect(style(fake).accent).toBe("#7a1f3d");
});

test("a name that is taken says so and keeps what was typed", async ({ page }) => {
  await open(page, [FOREST]);
  await panel(page).getByLabel("Name for this theme").fill("forest LOOK");
  await panel(page).getByRole("button", { name: "Save this look" }).click();
  await expect(panel(page).getByText("You already have a theme with that name.")).toBeVisible();
  await expect(panel(page).getByLabel("Name for this theme")).toHaveValue("forest LOOK");
});

test("deleting can be cancelled", async ({ page }) => {
  const fake = await open(page, [FOREST]);
  await page.getByRole("button", { name: "Delete Forest look" }).click();
  await page.getByRole("button", { name: "Keep" }).click();
  await expect(page.getByRole("button", { name: "Delete Forest look" })).toBeVisible();
  expect(fake.themes).toHaveLength(1);
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe: the themes panel with a theme, renaming and a delete question (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await open(page, [FOREST]);
    await axe(page);
    await page.getByRole("button", { name: "Delete Forest look" }).click();
    await axe(page);
    await page.getByRole("button", { name: "Keep" }).click();
    await page.getByRole("button", { name: "Rename Forest look" }).click();
    await axe(page);
  });
}

test("on a phone the panel fits and saves", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const fake = await fakeApi(page, { studio: withCanvas(), themes: [{ ...FOREST }] });
  await page.goto("/studio");
  await expect(page.locator("[data-el='name']")).toBeVisible();
  await page.getByRole("button", { name: "Page and style" }).click();
  await panel(page).getByRole("button", { name: "Use Forest look" }).scrollIntoViewIfNeeded();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await panel(page).getByRole("button", { name: "Use Forest look" }).click();
  await saved(page);
  expect(style(fake).accent).toBe(FOREST.accent);
});
