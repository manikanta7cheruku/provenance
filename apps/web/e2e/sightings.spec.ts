import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, makeJob, SAMPLE_MATCHES } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

async function open(page: Page, withMatches = true) {
  const fake = await fakeApi(page, {
    jobs: [makeJob("ready", { id: "job-1" })],
    matches: withMatches ? SAMPLE_MATCHES.map((m) => structuredClone(m)) : [],
  });
  await page.goto("/opportunities/job-1");
  await expect(page.getByRole("heading", { name: "Where else this job appears" })).toBeVisible();
  return fake;
}

test("it lists your copy and the copies found, and says why each match was made", async ({ page }) => {
  await open(page);
  await expect(page.getByText("Your copy")).toBeVisible();
  await expect(page.getByText("Pasted by you.")).toBeVisible();
  await expect(page.getByText(/Same company, title and place, and 92% of the wording matches/)).toBeVisible();
  await expect(page.getByText("Linked automatically")).toBeVisible();
  await expect(page.getByText("Possible match")).toBeVisible();
  await expect(page.getByRole("link", { name: /Open this posting at Greenhouse job boards/ })).toHaveAttribute("href", "https://boards.greenhouse.io/acme/9");
});

test("a person can say it is not the same job, and change their mind", async ({ page }) => {
  await open(page);
  const first = page.locator(".sightings__item").first();
  await first.getByRole("button", { name: /Not the same job, Data Engineer/ }).click();
  await expect(first.getByText("You said: not the same job")).toBeVisible();
  await expect(page.getByText("Greenhouse job boards. Published by Greenhouse job boards")).toHaveCount(0);
  await first.getByRole("button", { name: /Decide again/ }).click();
  await expect(first.getByText("Linked automatically")).toBeVisible();
});

test("a possible match is only confirmed when the person says so", async ({ page }) => {
  await open(page);
  const second = page.locator(".sightings__item").nth(1);
  await expect(second.getByRole("button", { name: /^Same job/ })).toBeVisible();
  await second.getByRole("button", { name: /^Same job/ }).click();
  await expect(second.getByText("You said: same job")).toBeVisible();
});

test("with nothing found it says so honestly", async ({ page }) => {
  await open(page, false);
  await expect(page.getByText(/does not mean it is not posted elsewhere/)).toBeVisible();
  await expect(page.locator(".sightings__item")).toHaveCount(0);
});

for (const theme of ["light", "dark"] as const) {
  test.describe(`axe (${theme})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    });

    test("the section with matches", async ({ page }) => {
      await open(page);
      await axe(page);
    });
  });
}
