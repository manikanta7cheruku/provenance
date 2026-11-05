import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi, makeJob } from "./fake-api";
import type { FakeJob } from "./fake-api";
import { newReports } from "./fake-reports";
import type { FakeReports } from "./fake-reports";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(
    results.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")),
    })),
  ).toEqual([]);
}

function jobs(): FakeJob[] {
  const day = (n: number) =>
    `2026-10-${String(10 + n).padStart(2, "0")}T09:00:00Z`;
  return [
    makeJob("ready", {
      id: "j3",
      title: "Staff engineer",
      company: "Acme",
      elig: "eligible",
      band: "strong",
      added: day(3),
    }),
    makeJob("ready", {
      id: "j2",
      title: "Data analyst",
      company: "Beta Labs",
      elig: "eligible",
      band: "good",
      added: day(2),
      dstate: "saved",
    }),
    makeJob("ready", {
      id: "j1",
      title: "SRE",
      company: "Gamma",
      elig: "uncertain",
      band: "review",
      added: day(1),
    }),
  ];
}

async function open(
  page: Page,
  reports: Partial<FakeReports> = {},
  url = "/opportunities",
) {
  await page.setViewportSize({ width: 1400, height: 1000 });
  const fake = await fakeApi(page, {
    jobs: jobs(),
    reports: newReports(reports),
  });
  await page.goto(url);
  await expect(page.getByRole("heading", { name: "Your jobs" })).toBeVisible();
  return fake;
}

const panel = (page: Page) => page.locator("details.export");

async function expand(page: Page) {
  await panel(page).locator("summary").click();
  await expect(
    panel(page).getByRole("button", { name: "Make report" }),
  ).toBeVisible();
}

test("export is a quiet disclosure that says what it does and what it costs", async ({
  page,
}) => {
  await open(page);
  await expect(panel(page).locator("summary")).toHaveText("Export these jobs");
  await expect(
    panel(page).getByRole("button", { name: "Make report" }),
  ).toBeHidden();
  await expand(page);
  await expect(panel(page)).toContainText(
    "Makes a report of the 3 jobs in this list",
  );
  await expect(panel(page)).toContainText("never sent anywhere");
  await expect(panel(page)).toContainText("not counted against your plan");
});

test("a report is asked for with the filters of the list, shown as being made, then ready to download", async ({
  page,
}) => {
  const fake = await open(page, {}, "/opportunities?view=saved");
  await expand(page);
  await expect(panel(page)).toContainText("the 1 job in this list");
  await panel(page).getByRole("button", { name: "Make report" }).click();
  const list = panel(page).getByRole("list", { name: "Your reports" });
  await expect(list).toContainText("Being made");
  await expect
    .poll(() => fake.reports.calls[0])
    .toContain('create:xlsx:{"view":"saved"');
  await expect(list).toContainText("Ready", { timeout: 15_000 });
  await expect(list).toContainText("4 jobs, 18 KB");
  await expect(list).toContainText("List: Saved");
  await expect(list).toContainText("Deleted on 12 Nov");
  const link = list.getByRole("link", { name: /^Download/ });
  await expect(link).toHaveAttribute("href", "/api/v1/reports/rep-1/download");
  await expect(link).toHaveAttribute(
    "download",
    "Provenance opportunities 2026-11-05.xlsx",
  );
});

test("the three formats are offered, and quotes are only an option for the two reports that read job by job", async ({
  page,
}) => {
  const fake = await open(page);
  await expand(page);
  const format = panel(page).getByLabel("Format");
  await expect(format.locator("option")).toHaveText([
    "Excel workbook (.xlsx)",
    "CSV (.csv)",
    "Word document (.docx)",
  ]);
  const quotes = panel(page).getByLabel("Include short evidence quotes");
  await expect(quotes).not.toBeChecked();
  await quotes.check();
  await panel(page).getByRole("button", { name: "Make report" }).click();
  await expect
    .poll(() => fake.reports.calls[0])
    .toMatch(/^create:xlsx:.*:quotes$/);
  await format.selectOption("csv");
  await expect(quotes).toBeHidden();
  await panel(page).getByRole("button", { name: "Make report" }).click();
  await expect
    .poll(() => fake.reports.calls[1])
    .toMatch(/^create:csv:.*:plain$/);
  await format.selectOption("docx");
  await expect(
    panel(page).getByText("A report you can read and edit"),
  ).toBeVisible();
});

test("a report that could not be made says so, keeps the jobs safe and can be tried again the same way", async ({
  page,
}) => {
  const fake = await open(
    page,
    { outcome: "failed" },
    "/opportunities?view=saved",
  );
  await expand(page);
  await panel(page).getByLabel("Format").selectOption("docx");
  await panel(page).getByRole("button", { name: "Make report" }).click();
  const list = panel(page).getByRole("list", { name: "Your reports" });
  await expect(list).toContainText("Could not be made", { timeout: 15_000 });
  await expect(list.getByRole("alert")).toContainText(
    "Your jobs are safe. Try again.",
  );
  await expect(list.getByRole("link", { name: /Download/ })).toHaveCount(0);
  fake.reports.outcome = "ready";
  await list.getByRole("button", { name: "Try again" }).click();
  await expect.poll(() => fake.reports.calls.length).toBe(2);
  expect(fake.reports.calls[1]).toBe(fake.reports.calls[0]); // the same format and the same filters
  await expect(list.getByText("Ready")).toBeVisible({ timeout: 15_000 });
});

test("when too many reports are being made the reason is shown in words", async ({
  page,
}) => {
  await open(page, {
    refuse:
      "Your other reports are still being made. Wait for one to finish, then ask again.",
  });
  await expand(page);
  await panel(page).getByRole("button", { name: "Make report" }).click();
  await expect(panel(page)).toContainText("That did not work");
  await expect(panel(page)).toContainText(
    "Wait for one to finish, then ask again.",
  );
});

test("a finished report can be deleted and the change is announced", async ({
  page,
}) => {
  const fake = await open(page);
  await expand(page);
  await panel(page).getByRole("button", { name: "Make report" }).click();
  const list = panel(page).getByRole("list", { name: "Your reports" });
  await expect(list.getByText("Ready")).toBeVisible({ timeout: 15_000 });
  await list.getByRole("button", { name: /^Delete/ }).click();
  await expect(
    panel(page).getByRole("list", { name: "Your reports" }),
  ).toHaveCount(0);
  await expect(panel(page).getByRole("status")).toHaveText(
    "The report was deleted.",
  );
  await expect.poll(() => fake.reports.calls).toContain("delete:rep-1");
});

test("an empty list cannot be exported and says why", async ({ page }) => {
  await open(page, {}, "/opportunities?view=archived");
  await expand(page);
  await expect(
    panel(page).getByRole("button", { name: "Make report" }),
  ).toBeDisabled();
  await expect(panel(page)).toContainText(
    "There are no jobs in this list to export.",
  );
});

test("a report still being made does not stop you using the page", async ({
  page,
}) => {
  await open(page, { outcome: "stay" });
  await expand(page);
  await panel(page).getByRole("button", { name: "Make report" }).click();
  await expect(panel(page)).toContainText("Being made");
  // A report that is stuck being made can still be deleted, which frees the slot.
  await expect(
    panel(page).getByRole("button", { name: /^Delete/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Staff engineer" }),
  ).toBeVisible();
});

test("it works from the keyboard alone", async ({ page }) => {
  await open(page);
  await panel(page).locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(panel(page).getByLabel("Format")).toBeVisible();
  await panel(page).getByRole("button", { name: "Make report" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    panel(page).getByRole("list", { name: "Your reports" }),
  ).toBeVisible();
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe: the export panel being made, ready and failed (${scheme})`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await open(page, {
      items: [
        {
          id: "rep-1",
          format: "xlsx",
          state: "ready",
          reads: 9,
          query: { view: "all" },
          quotes: false,
          created: "2026-11-05T09:30:00Z",
        },
        {
          id: "rep-2",
          format: "docx",
          state: "failed",
          reads: 9,
          query: { view: "saved" },
          quotes: true,
          created: "2026-11-05T09:20:00Z",
        },
        {
          id: "rep-3",
          format: "csv",
          state: "preparing",
          reads: 0,
          query: { view: "active" },
          quotes: false,
          created: "2026-11-05T09:10:00Z",
        },
      ],
      outcome: "stay",
      seq: 3,
    });
    await expand(page);
    await expect(
      panel(page).getByRole("list", { name: "Your reports" }),
    ).toContainText("Could not be made");
    await axe(page);
  });
}

test("on a phone nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fakeApi(page, {
    jobs: jobs(),
    reports: newReports({
      items: [
        {
          id: "rep-1",
          format: "xlsx",
          state: "ready",
          reads: 9,
          query: { view: "all" },
          quotes: true,
          created: "2026-11-05T09:30:00Z",
        },
      ],
      seq: 1,
    }),
  });
  await page.goto("/opportunities");
  await panel(page).locator("summary").click();
  await expect(
    panel(page).getByRole("list", { name: "Your reports" }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
