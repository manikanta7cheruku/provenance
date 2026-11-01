import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, newStudio, studioDoc } from "./fake-api";
import type { FakeStudio } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  // The preview frame holds the server-drawn resume with no scripts, so axe cannot run inside it.
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).exclude("iframe[title='Resume preview']").analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

const LABEL = "Data Intern, Kestrel Analytics";
const GOOD = {
  id: "s-1",
  unit_id: "b1:0",
  kind: "bullets",
  label: LABEL,
  before_lines: ["Cleaned six CSV sources with pandas"],
  after_lines: ["Cleaned six CSV sources with pandas for weekly SQL reporting"],
  reason: "Leads with the data work this job asks for.",
  requirements: [{ id: "r-1", text: "Strong SQL and Python (pandas)" }],
  citations: [{ chunk_id: "11111111-1111-4111-8111-111111111111", quote: "Skill: SQL", source: "profile", entry_type: "skill" }],
  claims: [
    { text: "sql", kind: "name", supported: true, source: "evidence" },
    { text: "pandas", kind: "job term", supported: true, source: "resume" },
  ],
  blocked: false,
  edited: false,
  status: "pending",
};
const BLOCKED = {
  ...GOOD,
  id: "s-2",
  unit_id: "b2:0",
  label: "B.E. Computer Science, BMS College of Engineering",
  before_lines: ["Studied databases"],
  after_lines: ["Built Looker dashboards for 60 stakeholders"],
  reason: "Matches the BI requirement.",
  requirements: [],
  citations: [],
  claims: [
    { text: "looker", kind: "name", supported: false, source: null },
    { text: "60", kind: "number", supported: false, source: null },
  ],
  blocked: true,
};

function withJob(extra: Partial<FakeStudio> = {}): FakeStudio {
  return {
    ...newStudio(),
    doc: studioDoc(),
    tailorJobs: [{ job_id: "job-1", title: "Data Analyst", company: "Kestrel" }],
    tailorSuggestions: [GOOD, BLOCKED],
    ...extra,
  };
}

async function suggest(page: Page, studio: FakeStudio = withJob()) {
  await page.setViewportSize({ width: 1400, height: 1000 });
  const fake = await fakeApi(page, { studio });
  await page.goto("/studio");
  await page.getByRole("button", { name: "Suggest changes" }).click();
  await expect(page.getByRole("heading", { name: /2 suggested changes, 2 waiting/ })).toBeVisible({ timeout: 10_000 });
  return fake;
}

test("with no checked job it says what to do and links to Opportunities", async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 1000 });
  await fakeApi(page, { studio: { ...newStudio(), doc: studioDoc() } });
  await page.goto("/studio");
  await expect(page.getByText(/Suggestions are made for a job you have checked/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Opportunities" }).last()).toHaveAttribute("href", "/opportunities");
});

test("suggestions are shown beside the old wording with the reason, evidence and checks", async ({ page }) => {
  await suggest(page);
  const card = page.locator(".tailor__card").first();
  await expect(card.getByRole("heading", { name: LABEL })).toBeVisible();
  await expect(card.getByText("Your resume now")).toBeVisible();
  await expect(card.getByText("Suggested", { exact: true })).toBeVisible();
  await expect(card.locator("ins")).toContainText("for weekly SQL reporting");
  await expect(card.getByText("Leads with the data work this job asks for.")).toBeVisible();
  await expect(card.getByText(/Strong SQL and Python/)).toBeVisible();
  await card.getByText(/Evidence this uses/).click();
  await expect(card.getByText("Skill: SQL")).toBeVisible();
  await expect(card.getByText(/Every fact checked/)).toBeVisible();
  await page.getByText(/Not added to your resume/).click();
  await expect(page.getByText("Experience with Tableau")).toBeVisible();
});

test("a suggestion that adds an unsupported fact is blocked and says which facts", async ({ page }) => {
  await suggest(page);
  const card = page.locator(".tailor__card").nth(1);
  await expect(card.locator(".tailor__bad")).toContainText("looker, 60");
  await expect(card.getByRole("button", { name: /^Accept change/ })).toBeDisabled();
  await expect(card.getByText(/cannot be applied while it adds something/)).toBeVisible();
});

test("accepting applies the change to the resume that is on the screen", async ({ page }) => {
  const fake = await suggest(page);
  await page.getByRole("button", { name: `Accept change, ${LABEL}` }).click();
  await expect(page.getByText("Applied to your resume.")).toBeVisible();
  expect(fake.studio.doc!.revision).toBe(2);
  expect(JSON.stringify(fake.studio.doc!.content)).toContain("for weekly SQL reporting");
  await expect(page.getByText(/Earlier wording is kept in Earlier versions/)).toBeAttached();
  await expect(page.getByRole("heading", { name: /2 suggested changes, 1 waiting/ })).toBeVisible();
});

test("rejecting leaves the resume alone", async ({ page }) => {
  const fake = await suggest(page);
  await page.getByRole("button", { name: `Reject change, ${LABEL}` }).click();
  await expect(page.getByText("Rejected. Your resume was not changed.")).toBeVisible();
  expect(fake.studio.doc!.revision).toBe(1);
});

test("editing a blocked suggestion re-checks it and can make it acceptable", async ({ page }) => {
  const fake = await suggest(page);
  const label = BLOCKED.label;
  await page.getByRole("button", { name: `Edit change, ${label}` }).click();
  const box = page.getByLabel(`Edit the suggested wording for ${label}`);
  await box.fill("Built SQL dashboards for the college project");
  await page.getByRole("button", { name: "Save my edit" }).click();
  const card = page.locator(".tailor__card").nth(1);
  await expect(card.getByText(/Every fact checked/)).toBeVisible();
  await expect(card.getByText(/You edited this suggestion/)).toBeVisible();
  await expect(page.getByRole("button", { name: `Accept change, ${label}` })).toBeEnabled();
  await page.getByRole("button", { name: `Edit change, ${label}` }).click();
  await page.getByLabel(`Edit the suggested wording for ${label}`).fill("Built Looker dashboards");
  await page.getByRole("button", { name: "Save my edit" }).click();
  await expect(card.locator(".tailor__bad")).toContainText("looker");
  expect(fake.studio.tailoring!.suggestions[1].blocked).toBe(true);
});

test("an empty edit is refused with a message next to the box", async ({ page }) => {
  await suggest(page);
  await page.getByRole("button", { name: `Edit change, ${LABEL}` }).click();
  await page.getByLabel(`Edit the suggested wording for ${LABEL}`).fill("   ");
  await page.getByRole("button", { name: "Save my edit" }).click();
  await expect(page.getByText(/Write between 1 and 8 lines/)).toBeVisible();
});

test("a model with nothing better to say gets an honest empty answer", async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 1000 });
  await fakeApi(page, { studio: withJob({ tailorSuggestions: [] }) });
  await page.goto("/studio");
  await page.getByRole("button", { name: "Suggest changes" }).click();
  await expect(page.getByRole("heading", { name: "No changes suggested" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/using only what your evidence supports/)).toBeVisible();
});

for (const theme of ["light", "dark"] as const) {
  test.describe(`axe (${theme})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    });

    test("the suggestions, a blocked one, and the edit box", async ({ page }) => {
      await suggest(page);
      await page.getByText(/Evidence this uses/).click();
      await page.getByText(/Not added to your resume/).click();
      await axe(page);
      await page.getByRole("button", { name: `Edit change, ${LABEL}` }).click();
      await axe(page);
    });
  });
}
