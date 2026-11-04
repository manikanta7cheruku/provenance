import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, makeJob } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

async function choose(page: Page, way: string) {
  await page.getByRole("radio", { name: way }).check({ force: true });
}

test("the four ways of adding a job are one choice, and paste is the first", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/opportunities");
  await expect(page.getByRole("heading", { name: "Add a job" })).toBeVisible();
  await expect(page.getByRole("radio", { name: "Paste text" })).toBeChecked();
  await expect(page.getByLabel("Job description")).toBeVisible();
  for (const [way, field] of [
    ["Type it in", "Job title"],
    ["From a link", "Web address of the posting"],
    ["From a spreadsheet", "Spreadsheet"],
  ] as const) {
    await choose(page, way);
    await expect(page.getByLabel(field, { exact: true })).toBeVisible();
  }
});

test("typing a job in: it needs a title and a description, then it is read", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/opportunities");
  await choose(page, "Type it in");
  await page.getByRole("button", { name: "Read this job" }).click();
  await expect(page.getByText("Enter the job title.")).toBeVisible();
  await page.getByLabel("Job title").fill("Backend engineer");
  await page.getByLabel("Company (optional)").fill("Acme");
  await page.getByLabel("What the job asks for").fill("You will build and run services in Python and PostgreSQL. Two years of experience are required.");
  await page.getByRole("button", { name: "Read this job" }).click();
  await expect(page).toHaveURL(/\/opportunities\/job-/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("a link: refused addresses explain themselves, a good one opens its report", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/opportunities");
  await choose(page, "From a link");
  const field = page.getByLabel("Web address of the posting");
  const go = page.getByRole("button", { name: "Read this page" });
  await field.fill("http://jobs.acme-careers.com/1");
  await go.click();
  await expect(page.getByText("Enter an address that starts with https://.")).toBeVisible();
  await field.fill("https://www.linkedin.com/jobs/view/1");
  await go.click();
  await expect(page.getByText(/does not allow automated reading/)).toBeVisible();
  await field.fill("https://localhost/admin");
  await go.click();
  await expect(page.getByText("That address is not on the public internet.")).toBeVisible();
  await field.fill("https://jobs.acme-careers.com/careers/1");
  await go.click();
  await expect(page).toHaveURL(/\/opportunities\/imports\/imp-/);
  await expect(page.getByRole("heading", { name: "Import report" })).toBeVisible();
  await expect(page.getByText(/You can leave this page/)).toBeVisible();
  await expect(page.getByText("Done", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: "Backend engineer" })).toBeVisible();
});

test("a spreadsheet: a wrong type is refused here, a good file ends in a report with every row", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/opportunities");
  await choose(page, "From a spreadsheet");
  await page.getByRole("button", { name: "Import these jobs" }).click();
  await expect(page.getByText("Choose a CSV or Excel file first.")).toBeVisible();
  await page.getByLabel("Spreadsheet", { exact: true }).setInputFiles({ name: "jobs.pdf", mimeType: "application/pdf", buffer: Buffer.from("x") });
  await expect(page.getByText(/This file type is not supported/)).toBeVisible();
  await page.getByLabel("Spreadsheet", { exact: true }).setInputFiles({ name: "jobs.csv", mimeType: "text/csv", buffer: Buffer.from("Description\nx") });
  await page.getByRole("button", { name: "Import these jobs" }).click();
  await expect(page).toHaveURL(/\/opportunities\/imports\/imp-/);
  await expect(page.getByText("Done, some rows need fixing")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: "Backend engineer" })).toBeVisible();
  await expect(page.getByText(/The link is not a web address/)).toBeVisible();
  await expect(page.getByText(/Columns that were not used: Salary/)).toBeVisible();
  await expect(page.getByRole("table", { name: /Import report, 2 rows/ })).toBeVisible();
});

test("a file that cannot be used says why and that nothing was added", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/opportunities");
  await choose(page, "From a spreadsheet");
  await page.getByLabel("Spreadsheet", { exact: true }).setInputFiles({ name: "bad.csv", mimeType: "text/csv", buffer: Buffer.from("Title\nx") });
  await page.getByRole("button", { name: "Import these jobs" }).click();
  await expect(page.getByText("This import could not be used")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/No column holds the job description/)).toBeVisible();
  await expect(page.getByText(/Nothing was added/)).toBeVisible();
});

test("recent imports are listed on the jobs page and open their report", async ({ page }) => {
  await fakeApi(page, {
    jobs: [makeJob("ready", { id: "job-1" })],
    imports: [{ id: "imp-1", kind: "csv", label: "october.csv", source: "Other" }],
    importReads: { "imp-1": 5 },
  });
  await page.goto("/opportunities");
  await expect(page.getByRole("heading", { name: "Recent imports" })).toBeVisible();
  await page.getByRole("link", { name: "october.csv" }).click();
  await expect(page).toHaveURL(/\/opportunities\/imports\/imp-1/);
  await expect(page.getByText("Done, some rows need fixing")).toBeVisible();
});

test("an unknown report is a clear message with a way back", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/opportunities/imports/nope");
  await expect(page.getByText(/could not be loaded/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to your jobs" })).toBeVisible();
});

for (const theme of ["light", "dark"] as const) {
  test(`axe: add a job, every way, and the report (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    await fakeApi(page, {
      imports: [{ id: "imp-1", kind: "xlsx", label: "october.xlsx", source: "Other" }],
      importReads: { "imp-1": 5 },
    });
    await page.goto("/opportunities");
    await expect(page.getByRole("heading", { name: "Recent imports" })).toBeVisible();
    for (const way of ["Paste text", "Type it in", "From a link", "From a spreadsheet"]) {
      await choose(page, way);
      await axe(page);
    }
    await page.getByRole("link", { name: "october.xlsx" }).click();
    await expect(page.getByText("Done, some rows need fixing")).toBeVisible();
    await axe(page);
  });
}
