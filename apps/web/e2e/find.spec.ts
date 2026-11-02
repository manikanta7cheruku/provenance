import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

async function open(page: Page) {
  await fakeApi(page);
  await page.goto("/find");
  await expect(page.getByRole("heading", { name: "Find jobs", level: 1 })).toBeVisible();
}

test("it is in the navigation and lists every source with where its terms were read", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Find jobs" })).toBeVisible();
  const lever = page.locator(".find__item", { hasText: "Lever postings" });
  await expect(lever.getByText(/Terms read and confirmed, terms read on 2026-11-02/)).toBeVisible();
  await expect(lever.getByRole("link", { name: /Read the terms of Lever postings/ })).toHaveAttribute("href", "https://www.lever.co/terms-of-service/");
  await expect(page.locator(".find__item", { hasText: "LinkedIn" }).getByText("Automated access not allowed")).toBeVisible();
});

test("a sentence becomes a plan that says what is imported and what is unavailable", async ({ page }) => {
  await open(page);
  await page.getByLabel("Describe the search").fill("Backend engineer in India");
  await page.getByRole("button", { name: "Plan this search" }).click();
  await expect(page.getByRole("status").filter({ hasText: /No source can be searched automatically/ })).toBeVisible();
  await expect(page.getByText("Read by the AI service.")).toBeVisible();
  await expect(page.getByText("Roles: Backend Engineer")).toBeVisible();
  await expect(page.getByText(/Work authorization comes from your profile: India/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "You import these" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Unavailable" })).toBeVisible();
  await expect(page.getByText(/Reason: It is switched off/).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Opportunities" }).last()).toHaveAttribute("href", "/opportunities");
});

test("an unclear company is put back to the person to choose", async ({ page }) => {
  await open(page);
  await page.getByLabel("Describe the search").fill("Tata jobs");
  await page.getByRole("button", { name: "Plan this search" }).click();
  const group = page.getByRole("group", { name: "Choose the company for Tata" });
  await expect(group.getByRole("button", { name: "Tata Motors" })).toBeVisible();
  await group.getByRole("button", { name: "Tata Consultancy Services" }).click();
  await expect(page.getByText("Read by the fields you set.")).toBeVisible();
});

test("the details can be filled in without the AI service", async ({ page }) => {
  await open(page);
  await page.getByText("Or fill in the details yourself").click();
  await page.getByLabel("Roles").fill("Data Analyst");
  await page.getByLabel("Companies").fill("Google");
  await page.getByRole("button", { name: "Plan with these details" }).click();
  await expect(page.getByText("Read by the fields you set.")).toBeVisible();
  await expect(page.getByText(/No permitted source can be searched for Google/)).toBeVisible();
});

test("a sentence without the AI service says so and an empty sentence cannot be sent", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("button", { name: "Plan this search" })).toBeDisabled();
  await page.getByLabel("Describe the search").fill("no key");
  await page.getByRole("button", { name: "Plan this search" }).click();
  await expect(page.getByText(/needs the AI service, which is not set up yet/)).toBeVisible();
});

test("jobs from a source that is searched are listed with their source and a link to the original", async ({ page }) => {
  await open(page);
  await page.getByLabel("Describe the search").fill("searchable Backend Engineer at Palantir");
  await page.getByRole("button", { name: "Plan this search" }).click();
  await expect(page.getByRole("heading", { name: "Jobs from the sources searched" })).toBeVisible();
  const job = page.locator(".find__item", { hasText: "Backend Engineer" }).first();
  await expect(job.getByText("Source: Lever postings")).toBeVisible();
  await expect(job.getByRole("link", { name: /Open the original posting for Backend Engineer/ })).toHaveAttribute("href", "https://jobs.lever.co/palantir/1");
  await expect(page.locator(".find__item", { hasText: "Data Analyst" })).toHaveCount(0);
});

test("a plan that searches nothing shows no job list and says how to add jobs", async ({ page }) => {
  await open(page);
  await page.getByLabel("Describe the search").fill("Backend engineer in India");
  await page.getByRole("button", { name: "Plan this search" }).click();
  await expect(page.getByRole("heading", { name: "Jobs from the sources searched" })).toHaveCount(0);
  await expect(page.getByText(/You can import jobs yourself/)).toBeVisible();
});

test("the source list shows when a source last answered and how many jobs are kept", async ({ page }) => {
  await open(page);
  const lever = page.locator(".find__item", { hasText: "Lever postings" }).last();
  await expect(lever.getByText("Healthy")).toBeVisible();
  await expect(lever.getByText(/Last answered/)).toBeVisible();
  await expect(lever.getByText(/2 open jobs kept/)).toBeVisible();
});

for (const theme of ["light", "dark"] as const) {
  test.describe(`axe (${theme})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    });

    test("the page with a plan and a company choice", async ({ page }) => {
      await open(page);
      await axe(page);
      await page.getByLabel("Describe the search").fill("Tata jobs");
      await page.getByRole("button", { name: "Plan this search" }).click();
      await expect(page.getByRole("heading", { name: "Companies" })).toBeVisible();
      await axe(page);
      await page.getByLabel("Describe the search").fill("searchable Backend Engineer at Palantir");
      await page.getByRole("button", { name: "Plan this search" }).click();
      await expect(page.getByRole("heading", { name: "Jobs from the sources searched" })).toBeVisible();
      await axe(page);
    });
  });
}
