import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, PARSED_ENTRIES, resumeBody } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(
    results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) })),
  ).toEqual([]);
}

async function search(page: Page, query: string) {
  await page.getByLabel("Search your entries").fill(query);
  await page.getByRole("button", { name: "Search", exact: true }).click();
}

for (const theme of ["light", "dark"] as const) {
  for (const meaning of ["off", "ready"] as const) {
    test(`axe: evidence search with results and with none, meaning search ${meaning} (${theme})`, async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
      await fakeApi(page, { resume: resumeBody("confirmed"), entries: PARSED_ENTRIES(), meaning });
      await page.goto("/profile");
      await search(page, "python");
      await expect(page.getByText("1 match, best first.")).toBeVisible();
      await axe(page);
      await search(page, "blockchain");
      await expect(page.getByText("No entry matches that.")).toBeVisible();
      await axe(page);
    });
  }
}

test("evidence search: status, validation, honest note and the link back to the entry", async ({ page }) => {
  await fakeApi(page, { resume: resumeBody("confirmed"), entries: PARSED_ENTRIES(), meaning: "off" });
  await page.goto("/profile");
  await expect(page.getByRole("status").filter({ hasText: "searchable by keyword" })).toContainText(
    "3 entries are searchable by keyword. Meaning search is off until an AI key is set up.",
  );

  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("Enter a word, a phrase or a question.")).toBeVisible();
  await expect(page.getByLabel("Search your entries")).toBeFocused();

  await page.getByLabel("Search your entries").fill("kestrel");
  await page.keyboard.press("Enter");
  await expect(page.getByText("1 match, best first.")).toBeVisible();
  await expect(page.getByText("Meaning search needs an AI key. Showing keyword matches only.")).toBeVisible();
  const hit = page.locator("li.evidence__hit");
  await expect(hit).toContainText("From your profile");
  await expect(hit).toContainText("Found by keyword");
  await hit.getByRole("link", { name: "Show in your entries" }).click();
  await expect(page).toHaveURL(/#entry-e2$/);
});

test("with meaning search ready the screen says so and labels both ways of finding", async ({ page }) => {
  await fakeApi(page, { resume: resumeBody("confirmed"), entries: PARSED_ENTRIES(), meaning: "ready" });
  await page.goto("/profile");
  await expect(page.getByText("Meaning search is ready.")).toBeVisible();
  await search(page, "python");
  await expect(page.locator("li.evidence__hit")).toContainText("Found by keyword and by meaning");
});

test("a profile with no entries says there is nothing to search and disables the button", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/profile");
  await expect(page.getByText("Nothing to search yet.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Search", exact: true })).toBeDisabled();
});
