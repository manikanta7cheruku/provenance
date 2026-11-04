import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, makeJob } from "./fake-api";
import type { FakeJob } from "./fake-api";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")) }))).toEqual([]);
}

function jobs(): FakeJob[] {
  const day = (n: number) => `2026-10-${String(10 + n).padStart(2, "0")}T09:00:00Z`;
  return [
    makeJob("ready", { id: "j5", title: "Staff engineer", company: "Acme", mode: "remote", place: "Pune, India", elig: "eligible", band: "strong", added: day(5), dstate: "approved_for_prep" }),
    makeJob("ready", { id: "j4", title: "Platform engineer", company: "Acme", mode: "hybrid", place: "Bengaluru, India", elig: "not_eligible", band: "not_eligible", added: day(4) }),
    makeJob("ready", { id: "j3", title: "Data analyst", company: "Beta Labs", mode: "remote", place: "Remote", elig: "eligible", band: "good", source: "Naukri", added: day(3), dstate: "saved", note: "Referred by Priya" }),
    makeJob("ready", { id: "j2", title: "SRE", company: "Gamma", mode: "onsite", place: "London, UK", elig: "uncertain", band: "review", added: day(2), dstate: "applied", appliedAt: "2026-10-20T12:00:00Z" }),
    makeJob("ready", { id: "j1", title: "Old role", company: "Gamma", added: day(1), dstate: "dismissed" }),
    makeJob("reading", { id: "j0", added: day(0) }),
  ];
}

async function open(page: Page, initial: FakeJob[] = jobs(), url = "/opportunities") {
  const fake = await fakeApi(page, { jobs: initial });
  await page.goto(url);
  if (url === "/opportunities") await expect(page.getByRole("heading", { name: "Your jobs" })).toBeVisible();
  return fake;
}

const rowOf = (page: Page, name: string) => page.getByRole("row").filter({ has: page.getByRole("link", { name }) });

test("the views show the right jobs with counts, and the choice lives in the address", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("button", { name: /^Active/ })).toContainText("4");
  await expect(rowOf(page, "Staff engineer")).toBeVisible();
  await expect(rowOf(page, "Old role")).toHaveCount(0); // dismissed is out of the Active view
  await page.getByRole("button", { name: /^Applications/ }).click();
  await expect(page).toHaveURL(/view=applications/);
  await expect(rowOf(page, "SRE")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Applied" })).toBeVisible();
  await page.getByRole("button", { name: /^Dismissed/ }).click();
  await expect(rowOf(page, "Old role")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: /^Dismissed/ })).toHaveAttribute("aria-current", "page");
});

test("search and filters narrow the list, show counts, and a link keeps them", async ({ page }) => {
  await open(page);
  await page.getByLabel("Search your jobs").fill("acme");
  await expect(page).toHaveURL(/q=acme/);
  await expect(rowOf(page, "Platform engineer")).toBeVisible();
  await expect(rowOf(page, "Data analyst")).toHaveCount(0);
  await page.getByText("Filters", { exact: true }).click();
  await page.getByLabel(/^Remote \(/).check();
  await expect(page).toHaveURL(/work_mode=remote/);
  await expect(rowOf(page, "Staff engineer")).toBeVisible();
  await expect(rowOf(page, "Platform engineer")).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("Search your jobs")).toHaveValue("acme");
  await expect(rowOf(page, "Staff engineer")).toBeVisible();
  await page.getByLabel("Search your jobs").fill("nothing like this");
  await expect(page.getByRole("heading", { name: "No jobs match" })).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).first().click();
  await expect(rowOf(page, "Staff engineer")).toBeVisible();
});

test("sorting by title and reversing the order", async ({ page }) => {
  await open(page);
  await page.getByLabel("Sort by").selectOption("title");
  await expect(page).toHaveURL(/sort=title/);
  const titles = async () => (await page.locator("tbody th a").allInnerTexts()).filter((t) => t !== "Untitled posting");
  await expect.poll(titles).toEqual(["Data analyst", "Platform engineer", "Staff engineer"]);
  await page.getByRole("button", { name: /Reverse order/ }).click();
  await expect(page).toHaveURL(/desc=true/);
});

test("the keyboard: move, save with undo, dismiss, search, select, and the shortcut list", async ({ page }) => {
  await open(page);
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("j");
  await expect(page.locator("tr[aria-current='true']")).toContainText("Platform engineer");
  await page.keyboard.press("s");
  await expect(page.getByText("Saved: Platform engineer.")).toBeVisible();
  await expect(rowOf(page, "Platform engineer").getByText("Saved")).toBeVisible();
  await page.getByRole("button", { name: "Unsave", exact: true }).click();
  await expect(page.getByText("Undone.")).toBeVisible();
  await expect(rowOf(page, "Platform engineer").getByText("New")).toBeVisible();
  await page.keyboard.press("d");
  await expect(page.getByText("Dismissed: Platform engineer.")).toBeVisible();
  await expect(rowOf(page, "Platform engineer")).toHaveCount(0);
  await page.keyboard.press("x");
  await expect(page.getByText("1 job selected")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByText("1 job selected")).toHaveCount(0);
  await page.keyboard.press("/");
  await expect(page.getByLabel("Search your jobs")).toBeFocused();
  await page.keyboard.type("jk"); // typing in a field never triggers a shortcut
  await expect(page.getByLabel("Search your jobs")).toHaveValue("jk");
  await page.getByLabel("Search your jobs").fill("");
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("?");
  await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("a shortcut for approving a job a hard rule rules out does nothing, and the button is not offered", async ({ page }) => {
  await open(page);
  await rowOf(page, "Platform engineer").click({ position: { x: 5, y: 5 } });
  const pane = page.getByRole("complementary", { name: "Selected job" });
  await expect(pane.getByRole("button", { name: /^Save:/ })).toBeVisible();
  await expect(pane.getByRole("button", { name: /^Approve for preparation:/ })).toHaveCount(0);
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("p");
  await expect(page.getByText(/Approved for preparation:/)).toHaveCount(0);
});

test("marking applied names the company and role, asks the day, and can be undone", async ({ page }) => {
  await open(page);
  await rowOf(page, "Data analyst").click({ position: { x: 5, y: 5 } });
  await page.getByRole("complementary", { name: "Selected job" }).getByRole("button", { name: /^Mark applied:/ }).click();
  const dialog = page.getByRole("dialog", { name: "Mark this job as applied?" });
  await expect(dialog).toContainText("Data analyst at Beta Labs");
  await expect(dialog).toContainText("never applies for you");
  await dialog.getByLabel("The day you applied").fill("2026-10-30");
  await dialog.getByRole("button", { name: "Mark applied" }).click();
  await expect(page.getByText("Marked as applied: Data analyst.")).toBeVisible();
  await page.getByRole("button", { name: /^Applications/ }).click();
  await expect(rowOf(page, "Data analyst")).toBeVisible();
  await page.getByRole("button", { name: "Undo applied", exact: true }).first().click();
  await expect(page.getByText("Undone.")).toBeVisible();
});

test("the pane shows the selected job and a note is saved only when asked", async ({ page }) => {
  await open(page);
  await rowOf(page, "Data analyst").click({ position: { x: 5, y: 5 } });
  const pane = page.getByRole("complementary", { name: "Selected job" });
  await expect(pane.getByRole("heading", { name: "Data analyst" })).toBeVisible();
  await expect(pane.getByLabel("Your note")).toHaveValue("Referred by Priya");
  await expect(pane.getByRole("button", { name: "Save note" })).toBeDisabled();
  await pane.getByLabel("Your note").fill("Referred by Priya. Call on Friday.");
  await pane.getByRole("button", { name: "Save note" }).click();
  await expect(pane.getByText("Note saved.")).toBeVisible();
  await expect(pane.getByRole("link", { name: "Open the full job" })).toHaveAttribute("href", "/opportunities/j3");
});

test("bulk: select several jobs, act on them together, and undo", async ({ page }) => {
  await open(page);
  await page.getByLabel(/^Select Staff engineer/).check();
  await page.getByLabel(/^Select Platform engineer/).check();
  const bulk = page.getByRole("group", { name: "Actions for the selected jobs" });
  await expect(bulk).toContainText("2 jobs selected");
  await expect(bulk.getByRole("button", { name: "Mark applied" })).toHaveCount(0); // one at a time: it asks for a day
  await bulk.getByRole("button", { name: "Dismiss" }).click();
  await expect(page.getByText(/Dismissed: 2 jobs\./)).toBeVisible();
  await expect(rowOf(page, "Staff engineer")).toHaveCount(0);
  await page.getByRole("button", { name: "Undo dismiss" }).click();
  await expect(page.getByText("Undone.")).toBeVisible();
  await expect(rowOf(page, "Staff engineer")).toBeVisible();
});

test("a bulk move says what it could not do", async ({ page }) => {
  await open(page);
  await page.getByLabel(/^Select Staff engineer/).check();
  await page.getByLabel(/^Select Data analyst/).check();
  const bulk = page.getByRole("group", { name: "Actions for the selected jobs" });
  await bulk.getByRole("button", { name: "Dismiss" }).click();
  await expect(page.getByText(/Dismissed: 2 jobs\./)).toBeVisible();
});

test("saved views: keep a view with its filters, apply it later, delete it", async ({ page }) => {
  await open(page);
  await page.getByText("Filters", { exact: true }).click();
  await page.getByLabel(/^Remote \(/).check();
  await page.getByRole("button", { name: "Save this view" }).click();
  await page.getByLabel("Name this view").fill("Remote roles");
  await page.getByRole("button", { name: "Save view" }).click();
  await expect(page.getByLabel("Saved views")).toHaveValue(/view-/);
  await page.getByRole("button", { name: "Save this view" }).click();
  await page.getByLabel("Name this view").fill("remote roles");
  await page.getByRole("button", { name: "Save view" }).click();
  await expect(page.getByText("You already have a saved view with that name.")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.goto("/opportunities");
  await page.getByLabel("Saved views").selectOption({ label: "Remote roles" });
  await expect(page).toHaveURL(/work_mode=remote/);
  await expect(rowOf(page, "Platform engineer")).toHaveCount(0);
  await page.getByRole("button", { name: "Delete this view" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete view" }).click();
  await expect(page.getByLabel("Saved views")).toContainText("None saved yet");
});

test("every view has an empty state that says what, why and what next", async ({ page }) => {
  await open(page, []);
  for (const [view, title] of [
    ["Active", "No jobs to look at"],
    ["Saved", "Nothing saved"],
    ["Applications", "No applications recorded"],
    ["Dismissed", "Nothing dismissed"],
    ["Archived", "Nothing archived"],
    ["All", "No jobs yet"],
  ] as const) {
    await page.getByRole("button", { name: new RegExp(`^${view}`) }).click();
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  }
});

test("on a narrow screen the pane gives way to the job page", async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 900 });
  await open(page);
  await expect(page.getByRole("complementary", { name: "Selected job" })).toHaveCount(0);
  await page.getByRole("link", { name: "Staff engineer" }).click();
  await expect(page).toHaveURL(/\/opportunities\/j5/);
});

test("the job page has the decision, a note, and an undo for the last action", async ({ page }) => {
  await open(page, jobs(), "/opportunities/j4");
  await expect(page.getByRole("heading", { name: "Your decision" })).toBeVisible();
  await page.getByRole("button", { name: /^Save:/ }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Unsave", exact: true }).first().click();
  await expect(page.getByRole("button", { name: /^Save:/ })).toBeVisible();
});

test("Find jobs can add a found job to your jobs", async ({ page }) => {
  await fakeApi(page);
  await page.goto("/find");
  await page.getByLabel("Describe the search").fill("searchable Backend Engineer at Palantir");
  await page.getByRole("button", { name: "Plan this search" }).click();
  await expect(page.getByRole("heading", { name: "Jobs from the sources searched" })).toBeVisible();
  const add = page.getByRole("button", { name: /Add to my jobs\s*:\s*Backend Engineer/ });
  await add.click();
  await expect(page.getByText("Added to your jobs.")).toBeVisible();
  await expect(page.getByRole("link", { name: /Open it/ })).toHaveAttribute("href", /\/opportunities\/job-/);
});

for (const theme of ["light", "dark"] as const) {
  test(`axe: the workbench, its pane, filters and dialogs (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    await open(page);
    await expect(page.getByRole("complementary", { name: "Selected job" })).toBeVisible();
    await axe(page);
    await page.getByText("Filters", { exact: true }).click();
    await axe(page);
    await page.getByLabel(/^Select Staff engineer/).check();
    await axe(page);
    await page.getByRole("button", { name: "Keyboard shortcuts" }).click();
    await axe(page);
    await page.keyboard.press("Escape");
    await rowOf(page, "Data analyst").click({ position: { x: 5, y: 5 } });
    await page.getByRole("complementary", { name: "Selected job" }).getByRole("button", { name: /^Mark applied:/ }).click();
    await axe(page);
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: /^Applications/ }).click();
    await axe(page);
  });

  test(`axe: empty views, saved views and the job page decision (${theme})`, async ({ page }) => {
    await page.addInitScript((value) => window.localStorage.setItem("pv-theme", value), theme);
    const fake = await open(page, []);
    await axe(page);
    fake.jobs = jobs();
    await page.goto("/opportunities/j3");
    await expect(page.getByRole("heading", { name: "Your decision" })).toBeVisible();
    await axe(page);
  });
}
