import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

// The profile screen against a small stateful fake of the API, so the whole flow (upload, reading,
// review, edit, add, remove, confirm, preferences) is exercised in a real browser in both themes.
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
import { fakeApi, PARSED_ENTRIES, resumeBody } from "./fake-api";
import type { Fake } from "./fake-api";

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

const STATES: [string, Partial<Fake>][] = [
  ["no resume and no entries", {}],
  ["reading", { resume: resumeBody("parsing") }],
  ["needs correction with entries", { resume: resumeBody("needs_correction"), entries: PARSED_ENTRIES() }],
  ["confirmed", { resume: resumeBody("confirmed"), entries: PARSED_ENTRIES() }],
  ["failed", { resume: resumeBody("failed", { error_message: "The reading service did not answer. Your file is safe. Try again in a few minutes." }) }],
];

for (const theme of ["light", "dark"] as const) {
  for (const [name, initial] of STATES) {
    test(`axe: profile with ${name} (${theme})`, async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
      await fakeApi(page, initial);
      await page.goto("/profile");
      await expect(page.getByRole("heading", { level: 1, name: "Profile" })).toBeVisible();
      await expect(page.getByRole("heading", { level: 2, name: "What you are looking for" })).toBeVisible();
      await axe(page);
    });
  }

  test(`axe: profile with an open edit form, add form and the delete dialog (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    await fakeApi(page, { resume: resumeBody("needs_correction"), entries: PARSED_ENTRIES() });
    await page.goto("/profile");
    await page.getByRole("button", { name: "Edit Kestrel Analytics" }).click();
    await page.getByRole("button", { name: "Skill", exact: true }).click();
    await axe(page);
    await page.getByRole("button", { name: "Remove Python" }).click();
    await expect(page.getByRole("dialog", { name: "Remove this entry?" })).toBeVisible();
    await axe(page);
  });
}

test("the whole journey: upload, reading, review, edit, add, remove, confirm, preferences", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/profile");

  await expect(page.getByRole("heading", { name: "Your profile has no entries yet" })).toBeVisible();
  await page.getByLabel("Resume", { exact: true }).setInputFiles({
    name: "Asha CV.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 sample"),
  });

  await expect(page.getByText("Reading your resume")).toBeVisible();
  await expect(page.getByText("Needs correction")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("1 suggested item was not in your resume text")).toBeVisible();
  const kestrel = page.locator("li.entry", { hasText: "Kestrel Analytics" });
  await expect(kestrel).toContainText("From your resume");
  await expect(kestrel).toContainText("Missing: Start, What you did");

  // Edit: the form opens in place, Escape cancels, then a real edit changes the provenance.
  await page.getByRole("button", { name: "Edit Kestrel Analytics" }).click();
  await page.getByLabel("Company", { exact: true }).fill("");
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Company", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Edit Kestrel Analytics" }).click();
  await page.getByLabel("Start (optional)").fill("2024-06");
  await page.getByLabel("What you did (optional)").fill("Built a delay report\nCleaned six data sources");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(kestrel).toContainText("Added or edited by you");
  await expect(kestrel).not.toContainText("Missing");

  // Add: a required field is enforced with a message and focus.
  await page.getByRole("button", { name: "Skill", exact: true }).click();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByLabel("Skill", { exact: true })).toBeFocused();
  await expect(page.getByText("This is required.")).toBeVisible();
  await page.getByLabel("Skill", { exact: true }).fill("Tableau");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.locator("li.entry", { hasText: "Tableau" })).toContainText("Added or edited by you");

  // Remove with a confirmation that names what is kept.
  await page.getByRole("button", { name: "Remove Python" }).click();
  const dialog = page.getByRole("dialog", { name: "Remove this entry?" });
  await expect(dialog).toContainText("Your resume file is not affected");
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  await dialog.getByRole("button", { name: "Remove entry" }).click();
  await expect(page.locator("li.entry", { hasText: "Python" })).toHaveCount(0);

  // Confirm the profile.
  await page.getByRole("button", { name: "Confirm anyway" }).click();
  await expect(page.getByText("Confirmed", { exact: true })).toBeVisible();

  // Preferences.
  await page.getByLabel("Roles you want").fill("Data analyst\nBackend engineer");
  await page.getByLabel("Where do you want to work from?").selectOption("hybrid");
  await page.getByLabel("Lowest yearly pay you would accept (optional)").fill("600000");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Choose a currency.")).toBeVisible();
  await page.getByLabel("Currency").selectOption("INR");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Preferences saved.")).toBeVisible();
});

test("a rejected file shows a sentence and keeps the upload available", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/profile");
  await page.getByLabel("Resume", { exact: true }).setInputFiles({
    name: "photo.png", mimeType: "image/png", buffer: Buffer.from("x"),
  });
  await expect(page.getByRole("alert").filter({ hasText: "not supported" })).toBeVisible();
  await expect(page.getByLabel("Resume", { exact: true })).toBeVisible();
});

test("the profile is reachable from the navigation and is no longer a placeholder", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/runs");
  await page.getByRole("link", { name: "Profile" }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.getByText("is not built yet")).toHaveCount(0);
});
