import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, makeJob } from "./fake-api";
import type { FakeAnalysis } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(
    results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) })),
  ).toEqual([]);
}

const analysis = (state: FakeAnalysis["state"], extra: Partial<FakeAnalysis> = {}): FakeAnalysis => ({
  state, reads: 0, ends: "ready", answered: false, feedback: {}, blocker: null, ...extra,
});

const CASES: { name: string; seed: Record<string, FakeAnalysis>; wait: string }[] = [
  { name: "not started", seed: {}, wait: "Check my evidence" },
  { name: "working", seed: { "job-1": analysis("working") }, wait: "Checking your evidence" },
  { name: "needs an answer", seed: { "job-1": analysis("needs_answer") }, wait: "Have you built dashboards in a course or project?" },
  { name: "ready", seed: { "job-1": analysis("ready") }, wait: "Worth a review" },
  { name: "failed", seed: { "job-1": analysis("failed") }, wait: "Continue checking" },
  { name: "blocked", seed: { "job-1": analysis("ready", { blocker: "Add your resume or a profile entry first." }) }, wait: "Worth a review" },
];

for (const theme of ["light", "dark"] as const) {
  for (const item of CASES) {
    test(`axe: evidence check ${item.name} (${theme})`, async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
      await fakeApi(page, { jobs: [makeJob("ready", { id: "job-1" })], analyses: item.seed });
      await page.goto("/opportunities/job-1");
      await expect(page.getByText(item.wait).first()).toBeVisible();
      if (item.name === "ready") {
        // Open the rows so the quotes and feedback buttons are checked too.
        for (const summary of await page.locator("summary.verdict__summary").all()) await summary.click();
      }
      await axe(page);
    });
  }
}

test("start, watch it work, answer the question, and read the result", async ({ page }) => {
  await fakeApi(page, { jobs: [makeJob("ready", { id: "job-1" })] });
  await page.goto("/opportunities/job-1");
  await page.getByRole("button", { name: "Check my evidence" }).click();
  await expect(page.getByText(/of 4 checked/)).toBeVisible();
  await expect(page.getByText("Worth a review")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("2 of 3 required requirements supported", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("What would change this")).toBeVisible();
});

test("the question is answered in place and the answer is cited as evidence", async ({ page }) => {
  await fakeApi(page, {
    jobs: [makeJob("ready", { id: "job-1" })],
    analyses: { "job-1": analysis("needs_answer") },
  });
  await page.goto("/opportunities/job-1");
  await page.getByRole("button", { name: "Use this answer" }).click();
  await expect(page.getByText("Write a short answer, or skip this question.")).toBeVisible();
  await expect(page.getByLabel("Have you built dashboards in a course or project?")).toBeFocused();
  await page.getByLabel("Have you built dashboards in a course or project?").fill("I built three Power BI dashboards.");
  await page.getByRole("button", { name: "Use this answer" }).click();
  await expect(page.getByText("Good match")).toBeVisible({ timeout: 15_000 });
  await page.locator("summary.verdict__summary", { hasText: "Build dashboards in a BI tool" }).click();
  await expect(page.getByText("From your answer")).toBeVisible();
});

test("skipping leaves the requirement unverified and finishes the check", async ({ page }) => {
  await fakeApi(page, { jobs: [makeJob("ready", { id: "job-1" })], analyses: { "job-1": analysis("needs_answer") } });
  await page.goto("/opportunities/job-1");
  await page.getByRole("button", { name: "Skip, leave it unverified" }).click();
  await expect(page.getByText("Checked", { exact: true })).toBeVisible();
});

test("feedback on a verdict is remembered and shown as chosen", async ({ page }) => {
  await fakeApi(page, { jobs: [makeJob("ready", { id: "job-1" })], analyses: { "job-1": analysis("ready") } });
  await page.goto("/opportunities/job-1");
  const row = page.locator("summary.verdict__summary", { hasText: "Write SQL" });
  await row.click();
  const group = page.getByRole("group", { name: "Feedback on: Write SQL to answer product questions" });
  await group.getByRole("button", { name: "No, this is wrong" }).click();
  await expect(group.getByRole("button", { name: "No, this is wrong" })).toHaveAttribute("aria-pressed", "true");
});

test("on a narrow screen nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await fakeApi(page, { jobs: [makeJob("ready", { id: "job-1" })], analyses: { "job-1": analysis("ready") } });
  await page.goto("/opportunities/job-1");
  await expect(page.getByText("Worth a review")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
