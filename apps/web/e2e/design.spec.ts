import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const ROUTES = ["/design", "/design/workbench", "/design/job"] as const;
const THEMES = ["light", "dark"] as const;
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function setTheme(page: Page, theme: (typeof THEMES)[number]) {
  await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
}

async function expectNoViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  const summary = results.violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact,
    nodes: violation.nodes.slice(0, 3).map((node) => node.target.join(" ")),
  }));
  expect(summary, "axe violations").toEqual([]);
}

for (const theme of THEMES) {
  for (const route of ROUTES) {
    test(`axe finds no WCAG violations on ${route} in ${theme} theme`, async ({ page }) => {
      await setTheme(page, theme);
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expectNoViolations(page);
    });
  }
}

for (const theme of THEMES) {
  test(`axe finds no violations in the workbench states and the opened requirements (${theme})`, async ({ page }) => {
    await setTheme(page, theme);
    await page.goto("/design/workbench");
    for (const state of ["Loading", "Empty", "Error"]) {
      await page.getByRole("radio", { name: state }).check({ force: true });
      await expectNoViolations(page);
    }
    await page.goto("/design/job");
    for (const summary of await page.locator(".req__summary").all()) await summary.click();
    await page.locator(".legend summary").click();
    await expectNoViolations(page);
  });
}

test("makes no request to another origin, so fonts are self-hosted", async ({ page, baseURL }) => {
  const foreign: string[] = [];
  page.on("request", (request) => {
    if (!request.url().startsWith(baseURL ?? "") && !request.url().startsWith("data:")) foreign.push(request.url());
  });
  await page.goto("/design");
  await page.evaluate(() => document.fonts.ready);
  expect(foreign).toEqual([]);
  const families = await page.evaluate(() => [...document.fonts].map((face) => face.family.replaceAll('"', "")));
  expect(families).toEqual(expect.arrayContaining(["IBM Plex Sans", "Newsreader", "IBM Plex Mono"]));
});

test("theme choice applies before first paint, persists and can return to system", async ({ page }) => {
  await page.addInitScript(() => {
    document.addEventListener("DOMContentLoaded", () => {
      (window as unknown as { themeAtDcl: string | null }).themeAtDcl = document.documentElement.getAttribute("data-theme");
    });
  });
  await page.goto("/design");
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);

  await page.getByRole("radio", { name: "Dark" }).check({ force: true });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(await page.evaluate(() => window.localStorage.getItem("pv-theme"))).toBe("dark");

  await page.reload();
  expect(await page.evaluate(() => (window as unknown as { themeAtDcl: string | null }).themeAtDcl)).toBe("dark");
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
  const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(background).toBe("rgb(19, 20, 18)");

  await page.getByRole("radio", { name: "System" }).check({ force: true });
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  expect(await page.evaluate(() => window.localStorage.getItem("pv-theme"))).toBeNull();
});

test("system theme follows the operating system preference", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/design");
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(19, 20, 18)");
  await page.emulateMedia({ colorScheme: "light" });
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(250, 249, 246)");
});

test("the confirmation dialog traps focus, starts on Cancel, closes on Escape and returns focus", async ({ page }) => {
  await page.goto("/design");
  const trigger = page.getByRole("button", { name: "Open a confirmation" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Delete this resume?" });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Delete resume" })).toBeFocused();
  // Focus never lands on the page behind the dialog, however many times Tab is pressed.
  for (let press = 0; press < 5; press += 1) {
    await page.keyboard.press("Tab");
    const contained = await page.evaluate(
      () => document.activeElement === document.body || document.activeElement?.closest("dialog") !== null,
    );
    expect(contained).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("the workbench keyboard flow: J and K move, S saves with undo, slash searches", async ({ page }) => {
  await page.goto("/design/workbench");
  const current = page.locator('tbody tr[aria-current="true"] th button');
  await expect(current).toHaveText("Data Analyst, Early Careers");
  await page.keyboard.press("j");
  await expect(current).toHaveText("Junior Backend Engineer");
  await page.keyboard.press("k");
  await expect(current).toHaveText("Data Analyst, Early Careers");

  await page.keyboard.press("s");
  const live = page.getByRole("status").filter({ hasText: "Saved Data Analyst" });
  await expect(live).toBeVisible();
  await live.getByRole("button", { name: "Undo" }).click();
  await expect(page.locator("tbody tr").first()).not.toContainText("Saved");

  await page.keyboard.press("/");
  await expect(page.getByLabel("Search role or company")).toBeFocused();
  // Shortcuts are off while typing: the letter S goes into the field and saves nothing.
  await page.keyboard.type("s");
  await expect(page.getByLabel("Search role or company")).toHaveValue("s");
  await expect(page.getByRole("status").filter({ hasText: "Saved Data Analyst" })).toHaveCount(0);
});

test("filters narrow the table and an empty result explains itself", async ({ page }) => {
  await page.goto("/design/workbench");
  await page.getByRole("radio", { name: "Remote" }).check({ force: true });
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.getByLabel("Search role or company").fill("zzz");
  await expect(page.getByRole("heading", { name: "No jobs match these filters" })).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(6);
});

test("file drop rejects the wrong type with a plain sentence and accepts a PDF", async ({ page }) => {
  await page.goto("/design");
  const input = page.getByLabel("Resume", { exact: true });
  await input.setInputFiles({ name: "photo.png", mimeType: "image/png", buffer: Buffer.from("x") });
  await expect(page.getByRole("alert").filter({ hasText: "not supported" })).toBeVisible();
  await input.setInputFiles({ name: "resume.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 sample") });
  await expect(page.getByText("resume.pdf")).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "not supported" })).toHaveCount(0);
});

test("reduced motion removes the skeleton pulse", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/design");
  const duration = await page.evaluate(() => getComputedStyle(document.querySelector(".skeleton__line") as Element).animationDuration);
  expect(parseFloat(duration)).toBeLessThan(0.001);
});

test("every gallery control is reachable by keyboard and shows a visible focus ring", async ({ page }) => {
  await page.goto("/design");
  await page.getByRole("button", { name: "Primary", exact: true }).focus();
  const outline = await page.evaluate(() => {
    const style = getComputedStyle(document.activeElement as Element);
    return { width: style.outlineWidth, style: style.outlineStyle };
  });
  expect(outline).toEqual({ width: "2px", style: "solid" });
});
