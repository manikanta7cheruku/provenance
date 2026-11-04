import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, makeJob } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

async function jobPage(page: Page, options: Parameters<typeof fakeApi>[1] = {}) {
  const fake = await fakeApi(page, { jobs: [makeJob("ready", { id: "job-1" })], ...options });
  await page.goto("/opportunities/job-1");
  await expect(page.getByRole("heading", { name: "Application drafts" })).toBeVisible();
  return fake;
}

const card = (page: Page, name: string) => page.getByRole("article", { name: `Draft: ${name}` });

test("a draft is always labelled, and the page says nothing is sent anywhere", async ({ page }) => {
  await jobPage(page);
  await expect(page.getByText(/Draft\. Written by AI from your own evidence\. Check every line\. Nothing is sent anywhere\./)).toBeVisible();
  await expect(page.getByText(/No drafts yet/)).toBeVisible();
});

test("a job that has not been checked cannot be written for, and says what to do", async ({ page }) => {
  await jobPage(page, { checked: false });
  await expect(page.getByText(/Check this job against your evidence first/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Write a cover note" })).toHaveCount(0);
});

test("a cover note is written, labelled, and every claim is found in the evidence", async ({ page }) => {
  await jobPage(page);
  await page.getByRole("button", { name: "Write a cover note" }).click();
  const note = card(page, "Cover note");
  await expect(note.getByText("Draft", { exact: true })).toBeVisible();
  await expect(note.getByLabel("Draft text")).toHaveValue(/I built 30 REST endpoints/, { timeout: 15_000 });
  await expect(note.getByText(/Every number, name and tool in this draft is in your evidence/)).toBeVisible();
  await expect(note.getByText(/Written by AI from your evidence\./)).toBeVisible();
  await note.getByText(/The evidence this draft may use/).click();
  await expect(note.getByText(/Built 30 REST endpoints with FastAPI/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Write a cover note" })).toBeDisabled(); // one cover note per job
});

test("editing checks every claim again: an invented fact is named, and removing it clears the warning", async ({ page }) => {
  await jobPage(page);
  await page.getByRole("button", { name: "Write a cover note" }).click();
  const note = card(page, "Cover note");
  const text = note.getByLabel("Draft text");
  await expect(text).toHaveValue(/I built 30/, { timeout: 15_000 });
  const save = note.getByRole("button", { name: "Save changes" });
  await expect(save).toBeDisabled();
  await text.fill("I built 30 REST endpoints with FastAPI. I also run Kubernetes clusters.");
  await save.click();
  await expect(note.getByText("Check these before you use this draft")).toBeVisible();
  await expect(note.locator("strong", { hasText: "kubernetes" })).toBeVisible();
  await expect(note.getByText(/Edited by you\./)).toBeVisible();
  await text.fill("I built 30 REST endpoints with FastAPI.");
  await note.getByRole("button", { name: "Save changes" }).click();
  await expect(note.getByText(/Every number, name and tool in this draft is in your evidence/)).toBeVisible();
});

test("an answer to a common question, and a question of your own", async ({ page }) => {
  await jobPage(page);
  await page.getByLabel("Answer a common question").selectOption({ label: "Why do you want to work here?" });
  await page.getByRole("button", { name: "Write an answer" }).click();
  const answer = card(page, "Why do you want to work here?");
  await expect(answer.getByLabel("Draft text")).toHaveValue(/Kubernetes/, { timeout: 15_000 });
  await expect(answer.getByText("Check these before you use this draft")).toBeVisible(); // the stand-in invents a fact
  await page.getByLabel("Answer a common question").selectOption("__custom__");
  await page.getByRole("button", { name: "Write an answer" }).click();
  await expect(page.getByText("Write the question you want to answer, or choose one from the list.")).toBeVisible();
  await page.getByLabel("Your question").fill("Describe a time you worked in a team.");
  await page.getByRole("button", { name: "Write an answer" }).click();
  await expect(card(page, "Describe a time you worked in a team.")).toBeVisible();
});

test("writing an edited draft again asks first, and cancelling keeps the edits", async ({ page }) => {
  await jobPage(page);
  await page.getByRole("button", { name: "Write a cover note" }).click();
  const note = card(page, "Cover note");
  await expect(note.getByLabel("Draft text")).toHaveValue(/I built 30/, { timeout: 15_000 });
  await note.getByLabel("Draft text").fill("My own careful words.");
  await note.getByRole("button", { name: "Save changes" }).click();
  await expect(note.getByText(/Edited by you\./)).toBeVisible();
  await note.getByRole("button", { name: /Write it again/ }).click();
  const dialog = page.getByRole("dialog", { name: "Write this draft again?" });
  await expect(dialog).toContainText("replaces your edits");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(note.getByLabel("Draft text")).toHaveValue("My own careful words.");
  await note.getByRole("button", { name: /Write it again/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Replace my edits" }).click();
  await expect(note.getByLabel("Draft text")).toHaveValue(/I built 30/, { timeout: 15_000 });
});

test("copying the text says so, and deleting a draft asks first", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await jobPage(page);
  await page.getByRole("button", { name: "Write a cover note" }).click();
  const note = card(page, "Cover note");
  await expect(note.getByLabel("Draft text")).toHaveValue(/I built 30/, { timeout: 15_000 });
  await note.getByRole("button", { name: "Copy text" }).click();
  await expect(note.getByText("Copied.")).toBeVisible();
  await note.getByRole("button", { name: /^Delete/ }).click();
  await page.getByRole("dialog", { name: "Delete this draft?" }).getByRole("button", { name: "Delete draft" }).click();
  await expect(note).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Write a cover note" })).toBeEnabled();
});

test("a draft that could not be written says why and can be tried again", async ({ page }) => {
  await jobPage(page);
  await page.getByLabel("Answer a common question").selectOption("__custom__");
  await page.getByLabel("Your question").fill("FAIL this question please?");
  await page.getByRole("button", { name: "Write an answer" }).click();
  await expect(page.getByText("This draft could not be written")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/The writing service did not answer/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Write it again/ })).toBeEnabled();
});

test("the shortlist is off by default, needs a verified address, and says what is sent", async ({ page }) => {
  await fakeApi(page, { verified: false });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Shortlist email" })).toBeVisible();
  await expect(page.getByText("Off. Nothing is sent.")).toBeVisible();
  await expect(page.getByText(/Verify your email address first/).first()).toBeVisible();
  await expect(page.getByLabel("Send me a shortlist email")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Send me one now" })).toBeDisabled();
  await expect(page.getByText(/It never applies for you/)).toBeVisible();
});

test("the shortlist is turned on with the person's own schedule, and the next time is shown", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/settings");
  await page.getByLabel("Send me a shortlist email").check();
  await page.getByLabel("How often").selectOption("daily");
  await expect(page.getByLabel("Day")).toHaveCount(0); // a daily email has no day
  await page.getByLabel("How often").selectOption("weekly");
  await page.getByLabel("Day").selectOption({ label: "Friday" });
  await page.getByLabel("Time", { exact: true }).selectOption("18");
  await page.getByLabel("Your time zone").selectOption("Europe/London");
  await page.getByLabel("How many jobs at most").selectOption("3");
  await page.getByRole("button", { name: "Save shortlist settings" }).click();
  await expect(page.getByText("Saved. The shortlist email is on.")).toBeVisible();
  await expect(page.getByText(/On\. Next email:/)).toBeVisible();
  await page.getByLabel("Send me a shortlist email").uncheck();
  await page.getByRole("button", { name: "Save shortlist settings" }).click();
  await expect(page.getByText("Off. Nothing is sent.")).toBeVisible();
});

test("the preview shows each job that would be sent with its reason, and says when there are none", async ({ page }) => {
  await fakeApi(page, {
    jobs: [
      makeJob("ready", { id: "a", title: "Backend engineer", company: "Acme", band: "strong", elig: "eligible" }),
      makeJob("ready", { id: "b", title: "Data analyst", company: "Beta", band: "review", elig: "eligible" }),
    ],
  });
  await page.goto("/settings");
  await page.getByRole("button", { name: "Preview what would be sent now" }).click();
  await expect(page.getByText("These are the jobs that would be in an email now.")).toBeVisible();
  const item = page.locator(".settings__items li");
  await expect(item).toHaveCount(1);
  await expect(item).toContainText("Backend engineer");
  await expect(item).toContainText("Strong match: 9 of 11 required requirements supported");
  await expect(page.getByRole("link", { name: "Backend engineer" })).toHaveAttribute("href", "/opportunities/a");
});

test("an empty preview says what a job needs", async ({ page }) => {
  await fakeApi(page, { jobs: [] });
  await page.goto("/settings");
  await page.getByRole("button", { name: "Preview what would be sent now" }).click();
  await expect(page.getByText(/Nothing would be sent now\. A job needs a finished evidence check/)).toBeVisible();
});

test("sending one now queues it and the history says who asked", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/settings");
  await page.getByRole("button", { name: "Send me one now" }).click();
  await expect(page.getByText(/Queued\. If anything is worth a look it will arrive shortly/)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("table", { name: /Recent shortlist emails/ })).toContainText("You asked for this one");
});

test("a time zone the server refuses is shown beside the field", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/settings");
  await page.getByLabel("Your time zone").evaluate((select: HTMLSelectElement) => {
    const option = document.createElement("option");
    option.value = "Mars/Base";
    option.text = "Mars/Base";
    select.append(option);
  });
  await page.getByLabel("Your time zone").selectOption("Mars/Base");
  await page.getByRole("button", { name: "Save shortlist settings" }).click();
  await expect(page.getByText("Choose a time zone from the list.")).toBeVisible();
});

for (const theme of ["light", "dark"] as const) {
  test(`axe: drafts in every state (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    await jobPage(page);
    await axe(page);
    await page.getByRole("button", { name: "Write a cover note" }).click();
    await axe(page); // working
    const note = card(page, "Cover note");
    await expect(note.getByLabel("Draft text")).toHaveValue(/I built 30/, { timeout: 15_000 });
    await note.getByText(/The evidence this draft may use/).click();
    await axe(page); // ready, with the evidence open
    await page.getByLabel("Answer a common question").selectOption({ label: "Why do you want to work here?" });
    await page.getByRole("button", { name: "Write an answer" }).click();
    await expect(card(page, "Why do you want to work here?").getByText("Check these before you use this draft")).toBeVisible({ timeout: 15_000 });
    await axe(page); // with a warning
    await note.getByLabel("Draft text").fill("Mine.");
    await note.getByRole("button", { name: "Save changes" }).click();
    await note.getByRole("button", { name: /Write it again/ }).click();
    await axe(page); // with the confirmation open
  });

  test(`axe: the shortlist settings, preview and history (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    await fakeApi(page, { jobs: [makeJob("ready", { id: "a", title: "Backend engineer", company: "Acme", band: "good", elig: "eligible" })], runs: [{ outcome: "sent", outcome_text: "Sent", item_count: 1, manual: false, at: "2026-11-02T08:00:00Z" }] });
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Shortlist email" })).toBeVisible();
    await axe(page);
    await page.getByRole("button", { name: "Preview what would be sent now" }).click();
    await expect(page.locator(".settings__items li")).toHaveCount(1);
    await axe(page);
  });
}
