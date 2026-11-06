import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

// The Evaluation page, with the API replaced by fixed answers so a passing run, a failing run, a
// comparison and the empty state can all be checked in a real browser.
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const CONFIG = { signup_mode: "invite", email_verification_required: false };
const ADMIN = {
  id: "11111111-1111-4111-8111-111111111111",
  email: "admin@example.com",
  role: "ADMIN",
  email_verified: true,
};
const GOOD = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const BAD = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const LLM = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(
    results.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")),
    })),
  ).toEqual([]);
}

const run = (id: string, over: Record<string, unknown> = {}) => ({
  id,
  created_at: "2026-11-05T09:00:00Z",
  suite: "deterministic",
  trigger: "ci",
  dataset_version: "jobs-v1",
  git_sha: "bf4e394230",
  model: null,
  passed: true,
  case_count: 892,
  failure_count: 18,
  regressions: [],
  ...over,
});
interface M {
  name: string;
  label: string;
  suite: string;
  value: number;
  baseline: number | null;
  limit: number;
  direction: string;
  status: string;
  delta: number | null;
  cases: number;
  previous: number | null;
  change: number | null;
}
const metric = (
  name: string,
  label: string,
  value: number,
  over: Record<string, unknown> = {},
): M => ({
  name,
  label,
  suite: "extraction",
  value,
  baseline: value,
  limit: 0.99,
  direction: "higher",
  status: "ok",
  delta: 0,
  cases: 2440,
  previous: null,
  change: null,
  ...over,
});
const GOOD_METRICS: M[] = [
  metric("requirement_recall", "Requirements kept when the model is right", 1),
  metric(
    "invented_leak_rate",
    "Invented requirements and facts that survive",
    0,
    { limit: 0, direction: "lower", cases: 300 },
  ),
  metric(
    "pairwise_agreement",
    "Pairs the scorer orders as a careful reader would",
    0.9865,
    { suite: "ranking", limit: 0.95, cases: 260 },
  ),
  metric(
    "injection_quoted_leak_rate",
    "Obeyed injections quoted verbatim that survive (known limit)",
    1,
    { limit: 1, direction: "lower", cases: 14 },
  ),
];
const FAILURES = [
  {
    suite: "extraction",
    case_id: "job-00-00/injection_quoted",
    expected: "instruction not kept as a requirement",
    got: "kept",
    note: "Known limit: a quoted injected sentence is real text in the posting, so grounding keeps it.",
  },
  {
    suite: "ranking",
    case_id: "only-preferred-few-supported over none-met",
    expected: "preferred shown first",
    got: "2.00 against 2.00",
    note: "",
  },
];
const SUITES = [
  { name: "extraction", cases: 528, failed: 14 },
  { name: "ranking", cases: 260, failed: 4 },
  { name: "claims", cases: 24, failed: 0 },
];
const detail = (
  r: ReturnType<typeof run>,
  metrics = GOOD_METRICS,
  against: ReturnType<typeof run> | null = null,
) => ({
  run: r,
  versions: {
    dataset: "jobs-v1",
    scoring: "scoring-1",
    eligibility_rules: "eligibility-1",
  },
  metrics,
  suites: SUITES,
  failures: FAILURES,
  against,
});
const BAD_METRICS: M[] = [
  metric(
    "requirement_recall",
    "Requirements kept when the model is right",
    0.9,
    { status: "below_limit", delta: -0.1 },
  ),
  metric(
    "invented_leak_rate",
    "Invented requirements and facts that survive",
    0.25,
    {
      limit: 0,
      direction: "lower",
      status: "below_limit",
      delta: 0.25,
      cases: 300,
    },
  ),
  metric(
    "pairwise_agreement",
    "Pairs the scorer orders as a careful reader would",
    0.9,
    {
      suite: "ranking",
      limit: 0.85,
      status: "regressed",
      baseline: 0.9865,
      delta: -0.0865,
      cases: 260,
    },
  ),
];

interface Mock {
  runs?: ReturnType<typeof run>[];
  calls?: string[];
}

async function open(page: Page, path = "/admin/evaluation", mock: Mock = {}) {
  const calls = mock.calls ?? [];
  const runs = mock.runs ?? [
    run(GOOD),
    run(BAD, {
      passed: false,
      failure_count: 40,
      regressions: [
        "requirement_recall",
        "invented_leak_rate",
        "pairwise_agreement",
      ],
      git_sha: "1234567890",
    }),
  ];
  await page.setViewportSize({ width: 1400, height: 1000 });
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const p = url.pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, json: body });
    calls.push(`${route.request().method()} ${p}${url.search}`);
    if (p === "/api/v1/status")
      return json({
        service: "provenance-api",
        version: "0.1.0",
        environment: "test",
        ready: true,
        checks: { database: "ok", migrations: "ok" },
      });
    if (p === "/api/v1/auth/session")
      return json({
        authenticated: true,
        user: ADMIN,
        csrf_token: "token",
        config: CONFIG,
      });
    if (p === "/api/v1/admin/evaluation") {
      const latest: Record<string, unknown> = {};
      for (const r of [...runs].reverse()) latest[r.suite] = r;
      return json({
        runs,
        latest,
        ranker: {
          adopt: false,
          labels: 39,
          people: 5,
          reasons: [
            "39 labels, and 1000 are needed before a comparison means anything.",
            "No candidate has been evaluated on held-out labels yet.",
          ],
        },
      });
    }
    const m = p.match(/^\/api\/v1\/admin\/evaluation\/([^/]+)$/);
    if (m) {
      const found = runs.find((r) => r.id === m[1]) ?? runs[0]!;
      const against =
        runs.find((r) => r.id === url.searchParams.get("against")) ?? null;
      if (found.id === BAD) {
        const metrics = BAD_METRICS.map((x) => ({
          ...x,
          previous: against ? 1 : null,
          change: against ? -0.1 : null,
        }));
        return json(detail(found, metrics, against));
      }
      const metrics = GOOD_METRICS.map((x) => ({
        ...x,
        previous: against ? x.value : null,
        change: against ? 0 : null,
      }));
      return json(detail(found, metrics, against));
    }
    return route.fulfill({ status: 404, json: { detail: "not mocked" } });
  });
  await page.goto(path);
  return calls;
}

test("the newest deterministic run opens first with every metric against its limit and baseline", async ({
  page,
}) => {
  // The first run in the list is the newest.
  await open(page, "/admin/evaluation", {
    runs: [run(GOOD), run(BAD, { passed: false })],
  });
  await expect(page.getByRole("heading", { name: "Evaluation" })).toBeVisible();
  await expect(page.locator(".console__headline")).toContainText("Passed");
  await expect(page.locator(".console__headline")).toContainText(
    "no worse than its baseline",
  );
  const metrics = page.getByRole("table", {
    name: "Every metric against its limit and its baseline",
  });
  await expect(
    metrics.getByRole("row", {
      name: /Requirements kept when the model is right/,
    }),
  ).toContainText("at least 0.99");
  await expect(
    metrics.getByRole("row", { name: /Invented requirements/ }),
  ).toContainText("at most 0.00");
  await expect(
    metrics.getByRole("row", { name: /Invented requirements/ }),
  ).toContainText("Within its limit");
  await expect(
    page.getByText("Versions: dataset jobs-v1, scoring scoring-1"),
  ).toBeVisible();
  await expect(page.getByText("None (rules only)")).toBeVisible();
});

test("a run that did not pass says which metrics and shows the cases that failed", async ({
  page,
}) => {
  await open(page, `/admin/evaluation?run=${BAD}`);
  await expect(page.locator(".console__headline")).toContainText(
    "Did not pass",
  );
  await expect(page.locator(".console__headline")).toContainText(
    "requirement_recall, invented_leak_rate, pairwise_agreement",
  );
  const metrics = page.getByRole("table", {
    name: "Every metric against its limit and its baseline",
  });
  await expect(
    metrics.getByRole("row", { name: /Requirements kept/ }),
  ).toContainText("Outside its limit");
  await expect(
    metrics.getByRole("row", { name: /Pairs the scorer/ }),
  ).toContainText("Worse than its baseline");
  const failed = page.getByRole("table", { name: /Failed cases/ });
  await expect(failed).toContainText("job-00-00/injection_quoted");
  await expect(failed).toContainText(
    "Known limit: a quoted injected sentence is real text",
  );
});

test("failures can be narrowed to one suite", async ({ page }) => {
  await open(page, `/admin/evaluation?run=${BAD}`);
  await page.getByLabel("Show failures from").selectOption("ranking");
  const failed = page.getByRole("table", { name: /Failed cases \(1 of/ });
  await expect(failed).toContainText(
    "only-preferred-few-supported over none-met",
  );
  await expect(failed).not.toContainText("injection_quoted");
});

test("choosing a run and a run to compare with changes what is shown and what is asked for", async ({
  page,
}) => {
  const calls = await open(page);
  await page.getByLabel("Run").selectOption(BAD);
  await expect(page.locator(".console__headline")).toContainText(
    "Did not pass",
  );
  await expect(page).toHaveURL(new RegExp(`run=${BAD}`));
  await page.getByLabel("Compare with").selectOption(GOOD);
  await expect(
    page.getByRole("columnheader", { name: "Against the other run" }),
  ).toBeVisible();
  await expect(page.getByText("Compared with the run of")).toBeVisible();
  await expect(
    page.getByRole("table", {
      name: "Every metric against its limit and its baseline",
    }),
  ).toContainText("-0.1000");
  expect(
    calls.some((c) => c.includes(`/admin/evaluation/${BAD}?against=${GOOD}`)),
  ).toBe(true);
});

test("each suite shows how many cases ran and how many failed", async ({
  page,
}) => {
  await open(page);
  const suites = page.getByRole("table", {
    name: "Cases run and failed in each suite",
  });
  await expect(
    suites.getByRole("row", { name: /Extraction \(grounding\)/ }),
  ).toContainText("528");
  await expect(
    suites.getByRole("row", { name: /Extraction \(grounding\)/ }),
  ).toContainText("14");
  await expect(
    suites.getByRole("row", { name: /Claim checking/ }),
  ).toContainText("24");
});

test("with nothing stored it says how to make the first run", async ({
  page,
}) => {
  await open(page, "/admin/evaluation", { runs: [] });
  await expect(
    page.getByText("No evaluation has been stored yet."),
  ).toBeVisible();
  await expect(
    page.getByText("python -m pv_eval run --store").first(),
  ).toBeVisible();
});

test("the learned ranker decision and the commands are on the page", async ({
  page,
}) => {
  await open(page);
  await expect(
    page.getByRole("heading", { name: "A learned ranker" }),
  ).toBeVisible();
  await expect(page.getByText("Not adopted.")).toBeVisible();
  await expect(page.getByText("at least 1,000 labels")).toBeVisible();
  await expect(
    page.getByText("Today there are 39 labels from 5 people."),
  ).toBeVisible();
  await expect(page.getByText("No candidate has been evaluated")).toBeVisible();
  await expect(
    page.getByText("python -m pv_eval run --update-baseline"),
  ).toBeVisible();
  await expect(page.getByText("The postings are invented")).toBeVisible();
});

test("the admin navigation lists Evaluation and marks it", async ({ page }) => {
  await open(page);
  const nav = page.getByRole("navigation", { name: "Administration" });
  await expect(nav.getByRole("link", { name: "Evaluation" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

for (const theme of ["light", "dark"] as const) {
  for (const [name, path, mock] of [
    ["a passing run", "/admin/evaluation", undefined],
    [
      "a failing run with a comparison",
      `/admin/evaluation?run=${BAD}&against=${GOOD}`,
      undefined,
    ],
    [
      "a model run",
      "/admin/evaluation",
      {
        runs: [
          run(LLM, { suite: "llm", model: "gemini-flash", trigger: "manual" }),
        ],
      },
    ],
    ["nothing stored", "/admin/evaluation", { runs: [] }],
  ] as [string, string, Mock | undefined][]) {
    test(`axe: ${name} (${theme})`, async ({ page }) => {
      await page.addInitScript(
        (value) => window.localStorage.setItem("pv-theme", value),
        theme,
      );
      await open(page, path, mock);
      await expect(
        page.getByRole("heading", { name: "A learned ranker" }),
      ).toBeVisible();
      if ((mock?.runs ?? [1]).length > 0)
        await expect(
          page.getByRole("table", {
            name: "Every metric against its limit and its baseline",
          }),
        ).toBeVisible();
      await axe(page);
    });
  }
}

test("on a phone nothing scrolls sideways", async ({ page }) => {
  await open(page, `/admin/evaluation?run=${BAD}&against=${GOOD}`);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("table", { name: /Failed cases/ })).toBeVisible();
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
