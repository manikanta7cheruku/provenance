import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, newStudio, studioDoc } from "./fake-api";
import type { FakeStudio } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  // The preview frame holds the resume document, drawn by the server and with no scripts, so axe
  // cannot run inside it. Its title is checked in the tests that open it.
  const results = await new AxeBuilder({ page })
    .withTags(WCAG_TAGS)
    .exclude("iframe[title='Resume preview']")
    .analyze();
  expect(
    results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) })),
  ).toEqual([]);
}

const withDoc = (extra: Partial<FakeStudio> = {}): FakeStudio => ({ ...newStudio(), doc: studioDoc(), ...extra });

for (const theme of ["light", "dark"] as const) {
  test.describe(`axe (${theme})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    });

    test("start screen", async ({ page }) => {
      await fakeApi(page);
      await page.goto("/studio");
      await expect(page.getByRole("button", { name: "Start my resume" })).toBeVisible();
      await axe(page);
    });

    test("editor: content, design, and the preview", async ({ page }) => {
      await fakeApi(page, { studio: withDoc() });
      await page.goto("/studio");
      await expect(page.getByLabel("Full name")).toHaveValue("Asha Rao");
      await expect(page.frameLocator("iframe[title='Resume preview']").getByRole("heading", { level: 1 })).toHaveText("Asha Rao");
      await axe(page);
      await page.getByRole("radio", { name: "Design" }).check({ force: true });
      await expect(page.getByRole("radio", { name: /Classic/ })).toBeChecked();
      await axe(page);
    });

    test("dialogs, conflict and export states", async ({ page }) => {
      await fakeApi(page, {
        studio: withDoc({ versions: [{ id: "v1", revision: 1, created_at: "2026-10-30T09:00:00Z" }], exportState: "ready" }),
      });
      await page.goto("/studio");
      await expect(page.getByRole("link", { name: /Download Asha Rao Resume.pdf/ })).toBeVisible();
      await axe(page);
      await page.getByRole("button", { name: "Earlier versions" }).click();
      await expect(page.getByRole("button", { name: "Restore version 1" })).toBeVisible();
      await axe(page);
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Delete this resume" }).click();
      await expect(page.getByRole("button", { name: "Delete resume" })).toBeVisible();
      await axe(page);
    });
  });
}

test("start from the profile, edit, and see it saved and previewed", async ({ page }) => {
  const fake = await fakeApi(page);
  await page.goto("/studio");
  await expect(page.getByRole("heading", { name: "Start your resume" })).toBeVisible();
  await page.getByRole("radio", { name: /Modern/ }).check({ force: true });
  await page.getByRole("button", { name: "Start my resume" }).click();
  await expect(page.getByLabel("Full name")).toBeVisible();

  await page.getByLabel("Full name").fill("Meera Nair");
  await expect(page.getByText("Changes not saved yet")).toBeVisible();
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });
  expect(fake.studio.doc?.content.header.name).toBe("Meera Nair");
  expect(fake.studio.doc?.revision).toBe(2);
  await expect(page.frameLocator("iframe[title='Resume preview']").getByRole("heading", { level: 1 })).toHaveText("Meera Nair");
});

test("the formatting toolbar works with the keyboard and saves marks", async ({ page }) => {
  const fake = await fakeApi(page, { studio: withDoc() });
  await page.goto("/studio");
  const toolbar = page.getByRole("toolbar", { name: /Formatting for Details: Data Intern/ });
  await expect(toolbar).toBeVisible();
  const bold = toolbar.getByRole("button", { name: "Bold" });
  await bold.focus();
  await page.keyboard.press("ArrowRight");
  await expect(toolbar.getByRole("button", { name: "Italic" })).toBeFocused();
  await page.keyboard.press("End");
  await expect(toolbar.getByRole("button", { name: "Numbered list" })).toBeFocused();
  await page.keyboard.press("Home");
  await expect(bold).toBeFocused();

  const editor = page.getByRole("textbox", { name: /Details: Data Intern/ });
  await editor.click();
  await page.keyboard.press("Control+A");
  await bold.click();
  await expect(bold).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });
  const saved = JSON.stringify(fake.studio.saves.at(-1));
  expect(saved).toContain('"type":"bold"');
});

test("sections move, with an announcement, and can be removed after a confirmation", async ({ page }) => {
  const fake = await fakeApi(page, { studio: withDoc() });
  await page.goto("/studio");
  await page.getByRole("button", { name: "Move down, Experience" }).click();
  await expect(page.getByText("Experience moved down to position 2.")).toBeAttached();
  await page.getByRole("button", { name: "Remove section, Education" }).click();
  await page.getByRole("button", { name: "Remove section", exact: true }).click();
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });
  expect(fake.studio.doc?.content.sections.map((s: { title: string }) => s.title)).toEqual(["Experience"]);
});

test("the design panel changes the template, refuses a light accent and takes a preset", async ({ page }) => {
  const fake = await fakeApi(page, { studio: withDoc() });
  await page.goto("/studio");
  await page.getByRole("radio", { name: "Design" }).check({ force: true });
  await page.getByRole("radio", { name: /Compact/ }).check({ force: true });
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });
  expect(fake.studio.doc?.content.style.template).toBe("compact");

  const color = page.getByLabel("Custom color");
  await color.fill("#ffee88");
  await expect(page.getByText(/too light to read on white paper/)).toBeVisible();
  await page.getByRole("button", { name: "Wine" }).click();
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 8000 });
  expect(fake.studio.doc?.content.style.accent).toBe("#7a1f3d");
});

test("a stale tab is told, and loading the newer version resumes work", async ({ page }) => {
  const fake = await fakeApi(page, { studio: withDoc({ conflict: true }) });
  await page.goto("/studio");
  await page.getByLabel("Full name").fill("From a stale tab");
  await expect(page.getByText("This resume was changed somewhere else", { exact: true }).first()).toBeVisible({ timeout: 8000 });
  await page.getByRole("button", { name: "Load the newer version" }).click();
  await expect(page.getByLabel("Full name")).toHaveValue("Asha Rao");
  expect(fake.studio.doc?.content.header.name).toBe("Asha Rao");
});

test("making a PDF saves first, shows progress and then the download link", async ({ page }) => {
  const fake = await fakeApi(page, { studio: withDoc() });
  await page.goto("/studio");
  await page.getByLabel("Full name").fill("Asha Rao");
  await page.getByLabel("Headline").fill("Data analyst");
  await page.getByRole("button", { name: "Make a PDF" }).click();
  await expect(page.getByRole("button", { name: "Making your PDF" })).toBeVisible();
  const link = page.getByRole("link", { name: /Download Asha Rao Resume.pdf/ });
  await expect(link).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/2 pages, 40 KB/)).toBeVisible();
  expect(fake.studio.doc?.content.header.headline).toBe("Data analyst");
  await expect(link).toHaveAttribute("href", "/api/v1/studio/exports/exp-1/download");
});

test("an earlier version can be restored", async ({ page }) => {
  await fakeApi(page, { studio: withDoc({ versions: [{ id: "v1", revision: 1, created_at: "2026-10-30T09:00:00Z" }] }) });
  await page.goto("/studio");
  await page.getByRole("button", { name: "Earlier versions" }).click();
  await page.getByRole("button", { name: "Restore version 1" }).click();
  await expect(page.getByLabel("Full name")).toHaveValue("Restored Name");
});

test("deleting the resume asks first and returns to the start screen", async ({ page }) => {
  await fakeApi(page, { studio: withDoc() });
  await page.goto("/studio");
  await page.getByRole("button", { name: "Delete this resume" }).click();
  await expect(page.getByText(/PDFs made from it are deleted/)).toBeVisible();
  await page.getByRole("button", { name: "Delete resume" }).click();
  await expect(page.getByRole("button", { name: "Start my resume" })).toBeVisible();
});

test("on a narrow screen the editor and the preview are shown one at a time and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await fakeApi(page, { studio: withDoc() });
  await page.goto("/studio");
  await expect(page.getByLabel("Full name")).toBeVisible();
  await expect(page.locator("iframe[title='Resume preview']")).toBeHidden();
  await page.getByRole("radio", { name: "Preview" }).check({ force: true });
  await expect(page.locator("iframe[title='Resume preview']")).toBeVisible();
  await expect(page.getByLabel("Full name")).toBeHidden();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("the studio is in the navigation", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/profile");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Resume studio" }).click();
  await expect(page).toHaveURL(/\/studio$/);
});
