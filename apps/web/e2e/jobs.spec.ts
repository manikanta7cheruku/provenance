import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, makeJob } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(
    results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) })),
  ).toEqual([]);
}

for (const theme of ["light", "dark"] as const) {
  for (const state of ["reading", "ready", "failed"] as const) {
    test(`axe: job detail while ${state} (${theme})`, async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
      await fakeApi(page, { jobs: [makeJob(state, { id: "job-1" })] });
      await page.goto("/opportunities/job-1");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      if (state === "ready") await expect(page.getByText("Can you take this job?")).toBeVisible();
      await axe(page);
    });
  }

  test(`axe: jobs list empty and filled (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    const fake = await fakeApi(page);
    await page.goto("/opportunities");
    await expect(page.getByRole("heading", { name: "Paste a job" })).toBeVisible();
    await axe(page);
    fake.jobs = [makeJob("ready", { id: "job-1" }), makeJob("failed", { id: "job-2", source: "Indeed" })];
    await page.reload();
    await expect(page.getByRole("link", { name: /Data Analyst/ })).toBeVisible();
    await axe(page);
  });
}

test("pasting: a short text is refused here, a real posting is read and shown", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/opportunities");
  await page.getByLabel("Job description").fill("too short");
  await page.getByRole("button", { name: "Read this job" }).click();
  await expect(page.getByText("This looks too short to be a job posting.")).toBeVisible();

  const posting = makeJob("reading").text.repeat(2);
  await page.getByLabel("Job description").fill(posting);
  await page.getByRole("button", { name: "Read this job" }).click();
  await expect(page).toHaveURL(/\/opportunities\/job-/);
  await expect(page.getByText("Reading the posting").first()).toBeVisible();
  await expect(page.getByText("Can you take this job?")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Must be authorized to work in India.").first()).toBeVisible();
});

test("pasting the same job again says nothing was read twice", async ({ page }) => {
  const existing = makeJob("ready", { id: "job-1" });
  await fakeApi(page, { jobs: [existing] });
  await page.goto("/opportunities");
  await page.getByLabel("Job description").fill(existing.text);
  await page.getByRole("button", { name: "Read this job" }).click();
  await expect(page.getByText("You pasted this job before, so nothing was read again.")).toBeVisible();
});

test("a failed reading can be read again, and a job can be deleted after a confirmation", async ({ page }) => {
  const fake = await fakeApi(page, { jobs: [makeJob("failed", { id: "job-1" })] });
  await page.goto("/opportunities/job-1");
  await expect(page.getByText("The reading service did not answer.")).toBeVisible();
  await page.getByRole("button", { name: "Read it again" }).click();
  await expect(page.getByText("Can you take this job?")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Delete this job" }).click();
  await page.getByRole("button", { name: "Delete job" }).click();
  await expect(page).toHaveURL(/\/opportunities$/);
  expect(fake.jobs).toHaveLength(0);
});

test("an unknown job is a calm not-found page", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/opportunities/missing");
  await expect(page.getByRole("heading", { name: "Job not found" })).toBeVisible();
});
