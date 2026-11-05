import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi } from "./fake-api";
import { newPrep } from "./fake-prep";
import type { FakePrep } from "./fake-prep";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const JOB = "job-1";

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

async function open(page: Page, prep: Partial<FakePrep> = {}) {
  await page.setViewportSize({ width: 1400, height: 1000 });
  const fake = await fakeApi(page, { prep: newPrep(prep) });
  await page.goto(`/opportunities/${JOB}/prepare`);
  await expect(page.getByRole("heading", { level: 1, name: "Prepare" })).toBeVisible();
  return fake;
}

const show = (page: Page, name: string) => page.getByRole("radio", { name }).check({ force: true });

test("what to prepare is ranked, explained and hedged", async ({ page }) => {
  await open(page);
  await expect(page.getByText(/Of 3 required things: 1 shown by your profile, 1 partly shown, 1 not shown/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Critical gaps (1)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "High-priority preparation areas (1)" })).toBeVisible();
  const critical = page.getByRole("region", { name: "Critical gaps" });
  await expect(critical).toContainText("Experience with AWS");
  await expect(critical).toContainText("does not show it yet");
  await expect(page.getByText("Not shown does not mean you cannot do it")).toBeVisible();
  await expect(page.getByText(/not a prediction of what will be asked/)).toBeVisible();
});

test("ticking things records progress", async ({ page }) => {
  await open(page);
  await expect(page.getByText("Progress: 0 of 2 done (0 percent)")).toBeVisible();
  const box = page.getByLabel("Experience with AWS");
  await box.click();
  await expect(page.getByText("Progress: 1 of 2 done (50 percent)")).toBeVisible();
  await expect(box).toBeChecked();
  await box.click();
  await expect(page.getByText("Progress: 0 of 2 done (0 percent)")).toBeVisible();
});

test("a job that has not been checked says so and offers the way to do it", async ({ page }) => {
  await open(page, { can_prepare: false });
  await expect(page.getByText("Check this job first")).toBeVisible();
  await expect(page.getByRole("link", { name: "Go to the job and run the evidence check" })).toBeVisible();
  await show(page, "Mock interview");
  await expect(page.getByRole("button", { name: "Start a practice interview" })).toBeDisabled();
});

test("practice material is written, shown with its evidence, and what is not shown is flagged", async ({ page }) => {
  const fake = await open(page);
  await show(page, "Practice material");
  const questions = page.getByRole("region", { name: "Interview questions" });
  await questions.getByRole("button", { name: "Write this" }).click();
  await expect.poll(() => fake.prep.calls).toContain("start:questions");
  await expect(questions.getByText("Writing, this takes a moment")).toBeVisible();
  await expect(questions.getByText("Tell me about your work with FastAPI.", { exact: true })).toBeVisible({ timeout: 10_000 });
  await questions.getByText("Tell me about your work with FastAPI.", { exact: true }).click();
  await expect(questions).toContainText("Built from 1 piece of your evidence");
  await questions.getByText("How would you approach AWS if you had not used it?", { exact: true }).click();
  await expect(questions).toContainText("does not currently contain enough evidence to answer this confidently");
  await expect(page.getByText(/Written for you from your own evidence/)).toBeVisible();
});

test("a claim that is not in the evidence is listed beside the item", async ({ page }) => {
  await open(page, { invented: true });
  await show(page, "Practice material");
  const questions = page.getByRole("region", { name: "Interview questions" });
  await questions.getByRole("button", { name: "Write this" }).click();
  await questions.getByText("Tell me about your work with FastAPI.", { exact: true }).click({ timeout: 10_000 });
  await expect(questions.getByText("Not in your evidence", { exact: true })).toBeVisible();
  await expect(questions.getByText("Kubernetes")).toBeVisible();
});

test("a failed write says why and can be tried again", async ({ page }) => {
  await open(page, { failWith: "The writing service is not set up yet. Try again later." });
  await show(page, "Practice material");
  const behavioral = page.getByRole("region", { name: "Behavioral prompts" });
  await behavioral.getByRole("button", { name: "Write this" }).click();
  await expect(behavioral.getByText("The writing service is not set up yet. Try again later.")).toBeVisible({ timeout: 10_000 });
  await expect(behavioral.getByRole("button", { name: "Write this" })).toBeEnabled();
});

test("a message is written for the person, checked, edited and copied, never sent", async ({ page }) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const fake = await open(page);
  await show(page, "Practice material");
  const outreach = page.getByRole("region", { name: "Outreach message" });
  await outreach.getByRole("button", { name: "Write this" }).click();
  const box = outreach.getByRole("textbox", { name: /Outreach message, in your words/ });
  await expect(box).toBeVisible({ timeout: 10_000 });
  await expect(box).toHaveValue(/I worked with this in my internship/);
  await expect(outreach).toContainText("Nothing is sent from here");
  await expect(outreach.getByText("Not in your evidence", { exact: true })).toHaveCount(0);
  await box.fill("I run Kubernetes for 400 users at Google and would value a conversation about the work.");
  await outreach.getByRole("button", { name: "Check my changes" }).click();
  await expect(outreach.getByText("Not in your evidence", { exact: true })).toBeVisible();
  await outreach.getByRole("button", { name: "Copy the text" }).click();
  await expect(outreach.getByText(/Copied/).first()).toBeVisible();
  // Writing it again after an edit asks first.
  await outreach.getByRole("button", { name: "Write again" }).click();
  await expect(page.getByRole("dialog", { name: "Write this again?" })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
  await expect.poll(() => fake.prep.outputs.outreach!.origin).toBe("edited");
  await outreach.getByRole("button", { name: "Write again" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Write it again" }).click();
  await expect(outreach.getByText("Writing, this takes a moment")).toBeVisible();
});

test("a mock interview asks one question at a time and scores each answer", async ({ page }) => {
  await open(page);
  await show(page, "Mock interview");
  await page.getByRole("button", { name: "Start a practice interview" }).click();
  await expect(page.getByRole("heading", { name: "Question 1 of 2" })).toBeVisible();
  await expect(page.getByText(/how would you approach learning it/)).toBeVisible();
  await page.getByLabel("Your answer").fill("idk");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText("Write your answer in a few sentences")).toBeVisible();
  await page.getByLabel("Your answer").fill("At my internship our team was cleaning a reporting job and I wrote SQL joins and reduced the nightly run from 40 minutes to 12. As a result the analysts had numbers on time.");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("heading", { name: "Feedback on your last answer" })).toBeVisible();
  await expect(page.getByText(/Structure, 3 of 3/)).toBeVisible();
  await expect(page.getByText("Next, practise this one: Building REST APIs with FastAPI")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Question 2 of 2" })).toBeVisible();
});

test("a claim in a mock answer that is not in the profile is named", async ({ page }) => {
  await open(page);
  await show(page, "Mock interview");
  await page.getByRole("button", { name: "Start a practice interview" }).click();
  await page.getByLabel("Your answer").fill("I led engineers at Google and shipped it with Kubernetes. As a result we saved a lot of money.");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText(/These are not in your profile: Kubernetes, Google/)).toBeVisible();
});

test("finishing shows every answer and its feedback, and a new one can be started", async ({ page }) => {
  await open(page);
  await show(page, "Mock interview");
  await page.getByRole("button", { name: "Start a practice interview" }).click();
  await page.getByLabel("Your answer").fill("At work I built the reporting job and it reduced the run from 40 minutes to 12 for the team.");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await page.getByRole("button", { name: "Finish now" }).click();
  await expect(page.getByText(/Finished. You answered 1 of 2 questions/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Start a new practice interview" })).toBeVisible();
  await expect(page.getByText("At work I built the reporting job")).toBeVisible();
});

test("the interview date makes a plan that ends with a review and a mock interview", async ({ page }) => {
  await open(page);
  await show(page, "Plan and company");
  await expect(page.getByText("No plan yet")).toBeVisible();
  const when = new Date(Date.now() + 6 * 86400000).toISOString().slice(0, 10);
  await page.getByLabel("Interview date").fill(when);
  await page.getByRole("button", { name: "Make the plan" }).click();
  const plan = page.getByRole("list", { name: "Day by day plan" });
  await expect(plan.getByRole("listitem")).toHaveCount(7);
  await expect(plan.getByRole("listitem").nth(5)).toContainText("Review");
  await expect(plan.getByRole("listitem").nth(6)).toContainText("Mock interview");
  await expect(plan.getByRole("listitem").first()).toContainText("Experience with AWS");
});

test("company notes are kept for the person and the link is never fetched", async ({ page }) => {
  const fake = await open(page);
  await show(page, "Plan and company");
  await expect(page.getByText("Place: Bengaluru")).toBeVisible();
  await expect(page.getByText("Nothing about the company here is invented")).toBeVisible();
  await page.getByLabel(/Company page you found/).fill("javascript:alert(1)");
  await page.getByRole("button", { name: "Save company notes" }).click();
  await expect(page.getByText(/It is never fetched/).first()).toBeVisible();
  await page.getByLabel(/Company page you found/).fill("https://example.com/about");
  await page.getByLabel("Your notes about the company").fill("Sells analytics tools to retailers.");
  await page.getByRole("button", { name: "Save company notes" }).click();
  await expect(page.getByRole("link", { name: "Open the company page" })).toHaveAttribute("href", "https://example.com/about");
  await expect.poll(() => fake.prep.company.notes).toBe("Sells analytics tools to retailers.");
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe: every tab of preparation with material, feedback and a plan (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await open(page, { invented: true, date: new Date(Date.now() + 4 * 86400000).toISOString().slice(0, 10) });
    await axe(page);
    await show(page, "Practice material");
    await page.getByRole("region", { name: "Interview questions" }).getByRole("button", { name: "Write this" }).click();
    await page.getByRole("region", { name: "Outreach message" }).getByRole("button", { name: "Write this" }).click();
    await expect(page.getByRole("textbox", { name: /Outreach message, in your words/ })).toBeVisible({ timeout: 10_000 });
    await page.getByText("Tell me about your work with FastAPI.", { exact: true }).click();
    await axe(page);
    await show(page, "Mock interview");
    await page.getByRole("button", { name: "Start a practice interview" }).click();
    await page.getByLabel("Your answer").fill("I led engineers at Google and shipped it with Kubernetes. As a result we saved a lot of money.");
    await page.getByRole("button", { name: "Get feedback" }).click();
    await expect(page.getByRole("heading", { name: "Feedback on your last answer" })).toBeVisible();
    await axe(page);
    await show(page, "Plan and company");
    await expect(page.getByRole("list", { name: "Day by day plan" })).toBeVisible();
    await axe(page);
  });
}

test("on a phone nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fakeApi(page, { prep: newPrep({ date: new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10) }) });
  await page.goto(`/opportunities/${JOB}/prepare`);
  for (const tab of ["What to prepare", "Practice material", "Mock interview", "Plan and company"]) {
    await page.getByRole("radio", { name: tab }).check({ force: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${tab} scrolls sideways on a phone`).toBeLessThanOrEqual(0);
  }
});
