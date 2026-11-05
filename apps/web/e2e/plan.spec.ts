import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { fakeApi } from "./fake-api";
import { newPlan } from "./fake-plan";
import type { FakePlan } from "./fake-plan";

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

const panel = (page: Page) =>
  page.getByRole("region", { name: "Your plan and usage" });

async function open(page: Page, plan: Partial<FakePlan> = {}) {
  await page.setViewportSize({ width: 1400, height: 1000 });
  await fakeApi(page, { plan: newPlan(plan) });
  await page.goto("/settings");
  await expect(panel(page)).toBeVisible();
}

test("it says which plan you are on and when the month starts again", async ({
  page,
}) => {
  await open(page);
  await expect(panel(page)).toContainText("You are on the Free plan");
  await expect(panel(page)).toContainText("starts again on 1 December");
  await expect(panel(page)).toContainText("are never counted");
});

test("every billable thing shows what was used in words and a bar", async ({
  page,
}) => {
  await open(page);
  const meters = panel(page).getByRole("list", { name: "Usage this month" });
  await expect(meters.getByRole("listitem")).toHaveCount(4);
  await expect(meters).toContainText("Job evidence checks");
  await expect(meters).toContainText("12 of 30 used");
  await expect(
    meters.getByRole("progressbar", {
      name: /Job evidence checks: 12 of 30 used/,
    }),
  ).toBeVisible();
  await expect(meters).toContainText(
    "Checking the same job again in the same month is free",
  );
});

test("nearly at a limit and at a limit say so in words, not only in color", async ({
  page,
}) => {
  await open(page, {
    used: {
      discovery_run: 17,
      job_analysis: 30,
      url_analysis: 0,
      material_generation: 3,
    },
  });
  const meters = panel(page).getByRole("list", { name: "Usage this month" });
  await expect(meters).toContainText("17 of 20 used. Nearly at the limit");
  await expect(meters).toContainText("30 of 30 used. The limit is reached");
});

test("a plan with no limit says so and has no bar", async ({ page }) => {
  await open(page, {
    plan_id: "pro",
    limits: {
      discovery_run: null,
      job_analysis: null,
      url_analysis: null,
      material_generation: null,
    },
  });
  const meters = panel(page).getByRole("list", { name: "Usage this month" });
  await expect(meters).toContainText("no limit on your plan");
  await expect(meters.getByRole("progressbar")).toHaveCount(0);
});

test("the plans are compared in a table with yours marked", async ({
  page,
}) => {
  await open(page);
  const table = panel(page).getByRole("table", {
    name: "What each plan includes each month",
  });
  await expect(
    table.getByRole("columnheader", { name: "Free (yours)" }),
  ).toBeVisible();
  await expect(
    table.getByRole("columnheader", { name: "Starter" }),
  ).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Pro" })).toBeVisible();
  const row = table.getByRole("row", { name: /Job evidence checks/ });
  await expect(row).toContainText("30");
  await expect(row).toContainText("150");
  await expect(row).toContainText("800");
  await expect(table.getByRole("row", { name: /Resumes kept/ })).toContainText(
    "10",
  );
});

test("changing plan is not available and says nothing is charged", async ({
  page,
}) => {
  await open(page);
  await expect(panel(page)).toContainText("Changing plan");
  await expect(panel(page)).toContainText(
    "Paid plans are not available yet. Nothing is charged",
  );
  await expect(
    panel(page).getByRole("button", { name: /upgrade|buy|pay|subscribe/i }),
  ).toHaveCount(0);
  await expect(panel(page)).toContainText("starting points");
});

test("what was counted recently is listed for the person", async ({ page }) => {
  await open(page);
  await panel(page).getByText("What was counted recently").click();
  await expect(panel(page)).toContainText("Job evidence checks, 1 unit");
  await expect(panel(page)).toContainText("Pieces of written material, 1 unit");
});

test("resumes and kept PDFs are shown", async ({ page }) => {
  await open(page);
  await expect(panel(page)).toContainText("Resumes: 1 of 1 kept");
  await expect(panel(page)).toContainText("PDFs kept for each resume: 5");
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe: the plan section in every meter state (${scheme})`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await open(page, {
      used: {
        discovery_run: 17,
        job_analysis: 30,
        url_analysis: 0,
        material_generation: 3,
      },
    });
    await axe(page);
    await panel(page).getByText("What was counted recently").click();
    await axe(page);
  });
}

test("on a phone nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fakeApi(page, { plan: newPlan() });
  await page.goto("/settings");
  await expect(panel(page)).toBeVisible();
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
