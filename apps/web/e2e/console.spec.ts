import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

// The admin console and the Run Inspector, with the API replaced by fixed answers so every state
// (healthy, critical, empty, failed) can be shown and checked in a real browser.
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const NOW = "2026-11-05T09:00:00Z";
const RUN = "3f2a1c90-1b2c-4d5e-8f60-123456789abc";
const JOB = "9d8c7b6a-1234-4abc-8def-0123456789ab";
const CONFIG = { signup_mode: "invite", email_verification_required: false };
const ADMIN = {
  id: "11111111-1111-4111-8111-111111111111",
  email: "admin@example.com",
  role: "ADMIN",
  email_verified: true,
};

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(
    results.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.slice(0, 2).map((n) => n.target.join(" ")),
    })),
  ).toEqual([]);
}

const COMPONENTS = [
  {
    name: "API",
    status: "ok",
    detail: "Version 0.1.0. 120 requests in the last 15 minutes.",
  },
  { name: "Database", status: "ok", detail: "Answering." },
  {
    name: "Migrations",
    status: "ok",
    detail: "The database matches the code.",
  },
  { name: "Workers", status: "ok", detail: "1 running." },
  { name: "Queue", status: "ok", detail: "Nothing is waiting." },
  {
    name: "Job sources",
    status: "ok",
    detail: "2 of 2 switched-on sources are healthy.",
  },
  {
    name: "Model provider",
    status: "unknown",
    detail: "No model calls in the last day.",
  },
  {
    name: "Evaluation",
    status: "unknown",
    detail: "No evaluation results yet. They arrive with checkpoint 3.6.",
  },
];
const THRESHOLDS = {
  queue_stale_warning_seconds: 300,
  queue_stale_critical_seconds: 1800,
  source_failure_streak: 3,
  llm_error_rate: 0.25,
  daily_spend_ceiling_usd: 0,
  server_error_rate: 0.05,
  p95_ms: 3000,
  auth_failures_per_hour: 50,
};
const HEALTHY = {
  status: "ok",
  headline: "Everything measured looks healthy.",
  version: "0.1.0",
  environment: "test",
  generated_at: NOW,
  components: COMPONENTS,
  alerts: [],
  requests: {
    measured: true,
    window_minutes: 15,
    requests: 120,
    server_errors: 0,
    client_errors: 3,
    p50_ms: 40,
    p95_ms: 210,
  },
  queue_by_state: { queued: 0 },
  oldest_waiting_seconds: null,
  trouble_tasks: [],
  sources: [
    {
      key: "lever",
      name: "Lever",
      enabled: true,
      status: "healthy",
      breaker_open: false,
      failure_streak: 0,
      last_success_at: NOW,
      last_failure_at: null,
    },
    {
      key: "ashby",
      name: "Ashby",
      enabled: false,
      status: "unknown",
      breaker_open: false,
      failure_streak: 0,
      last_success_at: null,
      last_failure_at: null,
    },
  ],
  security_24h: [],
  rate_limits_24h: [],
  thresholds: THRESHOLDS,
};
const TROUBLED = {
  ...HEALTHY,
  status: "critical",
  headline: "1 critical, 3 in all.",
  components: COMPONENTS.map((c) =>
    c.name === "Queue"
      ? {
          ...c,
          status: "critical",
          detail: "9 waiting, the oldest for 40 minutes.",
        }
      : c,
  ),
  alerts: [
    {
      key: "queue_stale",
      severity: "critical",
      title: "Work has been waiting a long time",
      detail: "The oldest waiting task is 40 minutes old and 9 are waiting.",
      action:
        "Look at what the workers are doing and whether one task is holding them up.",
      runbook: "operations/runbooks/alerts.md",
    },
    {
      key: "dead_letters",
      severity: "warning",
      title: "Tasks gave up",
      detail: "2 tasks were dead-lettered in the last day (5 in all).",
      action:
        "Open the dead letters, read the reason, fix the cause, then requeue what can be.",
      runbook: "operations/runbooks/alerts.md",
    },
    {
      key: "source_breaker_lever",
      severity: "warning",
      title: "Lever is paused after failures",
      detail: "The circuit breaker is open after 6 failures in a row.",
      action:
        "Read the source's fetch log. It retries by itself when the pause ends.",
      runbook: "operations/runbooks/alerts.md",
    },
  ],
  requests: {
    measured: false,
    window_minutes: 15,
    requests: 0,
    server_errors: 0,
    client_errors: 0,
    p50_ms: null,
    p95_ms: null,
  },
  queue_by_state: { queued: 7, retry_scheduled: 2 },
  oldest_waiting_seconds: 2400,
  trouble_tasks: [
    {
      id: "t1",
      task_type: "analyze_job",
      state: "retrying",
      attempts: 2,
      max_attempts: 4,
      run_id: RUN,
      last_error: "provider busy",
      run_after: NOW,
    },
    {
      id: "t2",
      task_type: "render_resume_pdf",
      state: "stuck",
      attempts: 1,
      max_attempts: 3,
      run_id: null,
      last_error: null,
      run_after: NOW,
    },
  ],
  sources: [
    {
      key: "lever",
      name: "Lever",
      enabled: true,
      status: "failing",
      breaker_open: true,
      failure_streak: 6,
      last_success_at: null,
      last_failure_at: NOW,
    },
  ],
  security_24h: [
    {
      action: "origin_rejected",
      label: "Requests blocked for their origin",
      count: 4,
    },
  ],
  rate_limits_24h: [{ policy: "studio_export_user", counters_over: 2 }],
  thresholds: { ...THRESHOLDS, daily_spend_ceiling_usd: 10 },
};
const USAGE = (days: number) => ({
  days,
  calls: 42,
  errors: 3,
  input_tokens: 12000,
  output_tokens: 3400,
  cost_usd: 0.084,
  accounts: 5,
  average_latency_ms: 640,
  highest_account_share: 0.5,
  daily_spend_ceiling_usd: 0,
  by_model: [
    {
      key: "gemini / flash",
      calls: 42,
      errors: 3,
      input_tokens: 12000,
      output_tokens: 3400,
      cost_usd: 0.084,
    },
  ],
  by_purpose: [
    {
      key: "analyze",
      calls: 30,
      errors: 2,
      input_tokens: 9000,
      output_tokens: 2400,
      cost_usd: 0.06,
    },
    {
      key: "extract",
      calls: 12,
      errors: 1,
      input_tokens: 3000,
      output_tokens: 1000,
      cost_usd: 0.024,
    },
  ],
  by_day: [
    {
      key: "2026-11-04",
      calls: 20,
      errors: 1,
      input_tokens: 5000,
      output_tokens: 1400,
      cost_usd: 0.04,
    },
    {
      key: "2026-11-05",
      calls: 22,
      errors: 2,
      input_tokens: 7000,
      output_tokens: 2000,
      cost_usd: 0.044,
    },
  ],
});
const TRACE = {
  run_id: RUN,
  found: true,
  tasks: [
    {
      id: "t1",
      task_type: "analyze_job",
      state: "dead_letter",
      attempts: 4,
      max_attempts: 4,
      last_error: "provider busy",
      created_at: NOW,
      finished_at: NOW,
      owner_email: "asha@example.com",
    },
  ],
  calls: [
    {
      purpose: "analyze",
      provider: "gemini",
      model: "flash",
      prompt_version: "analyze.v2",
      input_tokens: 900,
      output_tokens: 120,
      cost_usd: 0.002,
      latency_ms: 700,
      status: "error",
      error_class: "TRANSIENT",
      created_at: NOW,
    },
  ],
};
const SOURCES = [
  {
    key: "lever",
    display_name: "Lever",
    enabled: true,
    compliance_status: "verified",
    health_status: "healthy",
    last_success_at: NOW,
    last_failure_at: null,
    failure_streak: 0,
    breaker_open_until: null,
    jobs_open: 12,
    enable_blocker: null,
    review_expired: false,
  },
  {
    key: "greenhouse",
    display_name: "Greenhouse",
    enabled: true,
    compliance_status: "verified",
    health_status: "failing",
    last_success_at: null,
    last_failure_at: NOW,
    failure_streak: 6,
    breaker_open_until: "2099-01-01T00:00:00Z",
    jobs_open: 0,
    enable_blocker: null,
    review_expired: false,
  },
  {
    key: "adzuna",
    display_name: "Adzuna",
    enabled: false,
    compliance_status: "restricted",
    health_status: "unknown",
    last_success_at: null,
    last_failure_at: null,
    failure_streak: 0,
    breaker_open_until: null,
    jobs_open: 0,
    enable_blocker: "Its terms have not been confirmed.",
    review_expired: false,
  },
];
const FETCH_LOG = [
  {
    started_at: NOW,
    board_id: "acme",
    outcome: "rate_limited",
    http_status: 429,
    duration_ms: 310,
    jobs_seen: 0,
    jobs_new: 0,
    jobs_changed: 0,
    jobs_closed: 0,
    jobs_skipped: 0,
    error_class: "SOURCE_UNAVAILABLE",
  },
];

const run = (failed: boolean) => ({
  run: {
    id: RUN,
    workflow_type: "job_analysis",
    workflow_label: "Job analysis",
    ui_state: failed ? "retry_available" : "completed",
    created_at: NOW,
    started_at: NOW,
    finished_at: NOW,
    duration_ms: 4200,
  },
  error_summary: failed ? "LLMError: provider busy" : null,
  subject_label: "A job",
  subject_path: `/opportunities/${JOB}`,
  failure: failed
    ? {
        what: "The evidence check could not finish.",
        next: "Your profile and the job are unchanged. Run the check again from the job page.",
        retry_possible: true,
      }
    : null,
  totals: {
    steps: 2,
    steps_failed: failed ? 1 : 0,
    model_calls: 2,
    model_calls_failed: failed ? 1 : 0,
    input_tokens: 1800,
    output_tokens: 240,
    cost_usd: 0.004,
    models: ["gemini / flash"],
    prompt_versions: ["analyze.v2"],
  },
  steps: [
    {
      ordinal: 1,
      step_name: "gather_jobs",
      step_label: "Gather the jobs",
      ui_state: "completed",
      duration_ms: 120,
      error_summary: null,
      counts: { jobs: 7 },
    },
    {
      ordinal: 2,
      step_name: "write_file",
      step_label: "Write the file",
      ui_state: failed ? "permanently_failed" : "completed",
      duration_ms: 300,
      error_summary: null,
      counts: {},
    },
  ],
  llm_calls: [
    {
      purpose: "analyze",
      provider: "gemini",
      model: "flash",
      prompt_version: "analyze.v2",
      input_tokens: 900,
      output_tokens: 120,
      estimated_cost_usd: 0.002,
      latency_ms: 700,
      status: failed ? "error" : "ok",
    },
  ],
});

interface Mock {
  health?: unknown;
  trace?: unknown;
  runDetail?: unknown;
  calls?: string[];
}

async function open(page: Page, path: string, mock: Mock = {}) {
  const calls = mock.calls ?? [];
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
    if (p === "/api/v1/admin/health") return json(mock.health ?? HEALTHY);
    if (p === "/api/v1/admin/usage")
      return json(USAGE(Number(url.searchParams.get("days"))));
    if (p.startsWith("/api/v1/admin/trace/")) return json(mock.trace ?? TRACE);
    if (p === "/api/v1/admin/sources") return json(SOURCES);
    if (p.endsWith("/log")) return json(FETCH_LOG);
    if (p.endsWith("/poll"))
      return json({ message: "A fetch was queued." }, 202);
    if (p === `/api/v1/runs/${RUN}`) return json(mock.runDetail ?? run(true));
    return route.fulfill({ status: 404, json: { detail: "not mocked" } });
  });
  await page.goto(path);
  return calls;
}

// ------------------------------------------------------------------ health

test("a healthy system says so, with every part listed and nothing to do", async ({
  page,
}) => {
  await open(page, "/admin");
  await expect(page.getByRole("heading", { name: "Health" })).toBeVisible();
  await expect(page.locator(".console__headline")).toContainText(
    "Everything measured looks healthy.",
  );
  await expect(page.getByText("Nothing. Every rule is quiet.")).toBeVisible();
  const parts = page.getByRole("table", {
    name: "Each part and how it is doing",
  });
  await expect(parts.getByRole("row")).toHaveCount(9); // the header and eight parts
  await expect(parts.getByRole("row", { name: /Evaluation/ })).toContainText(
    "Not measured",
  );
  await expect(parts.getByRole("row", { name: /Evaluation/ })).toContainText(
    "3.6",
  );
  await expect(
    page.getByText(
      "In the last 15 minutes this API process answered 120 requests",
    ),
  ).toBeVisible();
  await expect(page.getByText("None. Nothing is being retried")).toBeVisible();
  await expect(
    page.getByText("No security events and no rate limit was exceeded."),
  ).toBeVisible();
});

test("the console navigation answers each operational question and marks where you are", async ({
  page,
}) => {
  await open(page, "/admin");
  const nav = page.getByRole("navigation", { name: "Administration" });
  await expect(nav.getByRole("link")).toHaveText([
    "Health",
    "Queue",
    "Sources",
    "Cost and usage",
    "Find a run",
    "Users",
    "Invites",
    "Audit log",
  ]);
  await expect(nav.getByRole("link", { name: "Health" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

test("alerts come with what to do first, and a task in trouble links to its run", async ({
  page,
}) => {
  await open(page, "/admin", { health: TROUBLED });
  await expect(page.locator(".console__headline")).toContainText(
    "1 critical, 3 in all.",
  );
  const alerts = page.getByRole("list", { name: "Alerts" });
  await expect(alerts.getByRole("listitem")).toHaveCount(3);
  await expect(alerts.getByRole("listitem").first()).toContainText("Critical");
  await expect(alerts.getByRole("listitem").first()).toContainText(
    "Do first: Look at what the workers are doing",
  );
  await expect(alerts.getByRole("listitem").first()).toContainText(
    "Runbook: operations/runbooks/alerts.md",
  );
  await expect(alerts).toContainText("Lever is paused after failures");
  const trouble = page.getByRole("table", { name: "Tasks to look at first" });
  await expect(trouble.getByRole("row", { name: /analyze_job/ })).toContainText(
    "Retrying",
  );
  await expect(
    trouble.getByRole("row", { name: /render_resume_pdf/ }),
  ).toContainText("Stuck");
  await expect(
    trouble.getByRole("link", { name: "Trace this run" }),
  ).toHaveAttribute("href", `/admin/runs?run=${RUN}`);
  await expect(
    page.getByText(
      "Not measured yet. This API process has not answered a request",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Switched-on job sources" }),
  ).toContainText("Paused after failures");
  await expect(
    page.getByRole("table", { name: "Security events" }),
  ).toContainText("Requests blocked for their origin");
  await expect(
    page.getByRole("table", { name: /Rate limits exceeded/ }),
  ).toContainText("studio export user");
});

test("the thresholds are shown as starting points, in words", async ({
  page,
}) => {
  await open(page, "/admin", { health: TROUBLED });
  await page.getByText("How these alerts are decided").click();
  await expect(
    page.getByText(
      "starting points chosen before there was traffic to measure",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Model spend is flagged at 80 percent of $10.00 a day."),
  ).toBeVisible();
  await expect(
    page.getByText("A source that fails 3 times in a row is flagged."),
  ).toBeVisible();
});

test("a failed health check says so and can be tried again", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    if (p === "/api/v1/auth/session")
      return route.fulfill({
        json: {
          authenticated: true,
          user: ADMIN,
          csrf_token: "t",
          config: CONFIG,
        },
      });
    if (p === "/api/v1/status")
      return route.fulfill({
        json: {
          service: "x",
          version: "1",
          environment: "t",
          ready: true,
          checks: { database: "ok", migrations: "ok" },
        },
      });
    return route.fulfill({
      status: 500,
      json: {
        code: "INTERNAL_ERROR",
        failure_class: "INTERNAL_ERROR",
        message: "Something went wrong on our side.",
      },
    });
  });
  await page.goto("/admin");
  await expect(page.getByRole("alert")).toContainText("Something went wrong");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

// ------------------------------------------------------------------ cost and usage

test("cost is added up by model, operation and day, and names nobody", async ({
  page,
}) => {
  const calls = await open(page, "/admin/usage");
  await expect(
    page.getByRole("heading", { name: "Cost and usage" }),
  ).toBeVisible();
  await expect(page.getByText("$0.08").first()).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Cost by model, last 7 days" }),
  ).toContainText("gemini / flash");
  await expect(
    page.getByRole("table", { name: "Cost by operation, last 7 days" }),
  ).toContainText("analyze");
  await expect(
    page.getByRole("table", { name: "Cost by day, last 7 days" }),
  ).toContainText("2026-11-05");
  await expect(
    page.getByText(
      "The account that used the most made up 50 percent of the cost.",
    ),
  ).toBeVisible();
  await expect(page.getByText("No daily spend ceiling is set")).toBeVisible();
  await page.getByLabel("Period").selectOption("30");
  await expect(
    page.getByRole("table", { name: "Cost by model, last 30 days" }),
  ).toBeVisible();
  expect(calls.some((c) => c.includes("/admin/usage?days=30"))).toBe(true);
});

// ------------------------------------------------------------------ find a run

test("a run reference finds the queue's tasks and the model calls, and shows nothing the person wrote", async ({
  page,
}) => {
  await open(page, "/admin/runs");
  await page.getByLabel("Run reference").fill(RUN);
  await page.getByRole("button", { name: "Find" }).click();
  const tasks = page.getByRole("table", { name: "Queue tasks for this run" });
  await expect(tasks).toContainText("analyze_job");
  await expect(tasks).toContainText("dead letter");
  await expect(tasks).toContainText("4 of 4");
  await expect(tasks).toContainText("asha@example.com");
  await expect(
    page.getByRole("table", { name: /Model calls for this run/ }),
  ).toContainText("analyze.v2");
  await expect(
    page.getByRole("table", { name: /Model calls for this run/ }),
  ).toContainText("Failed (TRANSIENT)");
  await expect(page).toHaveURL(new RegExp(`runs\\?run=${RUN}`));
});

test("a link from the health page opens the run already traced", async ({
  page,
}) => {
  await open(page, `/admin/runs?run=${RUN}`);
  await expect(
    page.getByRole("table", { name: "Queue tasks for this run" }),
  ).toBeVisible();
  await expect(page.getByLabel("Run reference")).toHaveValue(RUN);
});

test("something that is not a reference is explained, and an unknown run is not an error", async ({
  page,
}) => {
  await open(page, "/admin/runs", {
    trace: { run_id: RUN, found: false, tasks: [], calls: [] },
  });
  await page.getByLabel("Run reference").fill("hello");
  await page.getByRole("button", { name: "Find" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "That is not a run reference",
  );
  await page.getByLabel("Run reference").fill(RUN);
  await page.getByRole("button", { name: "Find" }).click();
  await expect(
    page.getByText("Nothing in the queue or the model log mentions this run."),
  ).toBeVisible();
});

// ------------------------------------------------------------------ sources

test("each source shows how it is doing, its recent fetches, and can be fetched now", async ({
  page,
}) => {
  const calls = await open(page, "/admin/sources");
  const table = page.getByRole("table", { name: "Job sources" });
  await expect(table.getByRole("row", { name: /Lever/ })).toContainText(
    "Healthy",
  );
  await expect(table.getByRole("row", { name: /Greenhouse/ })).toContainText(
    "Paused after failures",
  );
  await expect(table.getByRole("row", { name: /Adzuna/ })).toContainText(
    "Switched off",
  );
  await expect(table.getByRole("row", { name: /Adzuna/ })).toContainText(
    "Its terms have not been confirmed.",
  );
  await expect(table.getByRole("button", { name: /Fetch now/ })).toHaveCount(2); // not for the one that is off
  await table
    .getByRole("button", { name: /Recent fetches for Greenhouse/ })
    .click();
  await expect(
    page.getByRole("table", { name: "Recent fetches, newest first" }),
  ).toContainText("rate limited (SOURCE_UNAVAILABLE)");
  await table.getByRole("button", { name: /Fetch now from Lever/ }).click();
  await expect(page.getByText("A fetch was queued.")).toBeVisible();
  expect(calls.some((c) => c === "POST /api/v1/admin/sources/lever/poll")).toBe(
    true,
  );
});

// ------------------------------------------------------------------ the person's Run Inspector

test("a failed run explains itself in plain words, with numbers and a way back to the job", async ({
  page,
}) => {
  await open(page, `/runs/${RUN}`);
  await expect(
    page.getByRole("heading", { name: "Job analysis" }),
  ).toBeVisible();
  const problem = page.getByRole("alert");
  await expect(problem).toContainText("The evidence check could not finish.");
  await expect(problem).toContainText(
    "What to do: Your profile and the job are unchanged.",
  );
  await expect(problem).toContainText(
    "Technical note: LLMError: provider busy",
  );
  await expect(page.getByRole("link", { name: "A job" })).toHaveAttribute(
    "href",
    `/opportunities/${JOB}`,
  );
  const totals = page
    .getByRole("list", { name: "This run in numbers" })
    .or(page.locator("dl.runs__totals"));
  await expect(totals).toContainText("2, 1 failed");
  await expect(totals).toContainText("1,800 and 240");
  await expect(totals).toContainText("gemini / flash");
  await expect(totals).toContainText("analyze.v2");
  await expect(page.getByText(`Reference: ${RUN}`)).toBeVisible();
  await expect(
    page.getByText("never the text of your jobs or your resume"),
  ).toBeVisible();
});

test("steps use plain labels and show their counts", async ({ page }) => {
  await open(page, `/runs/${RUN}`);
  const steps = page.locator(".runs__steps");
  await expect(steps).toContainText("Gather the jobs");
  await expect(steps).toContainText("(jobs 7)");
  await expect(steps).toContainText("Write the file");
});

test("a run that worked has no problem box", async ({ page }) => {
  await open(page, `/runs/${RUN}`, { runDetail: run(false) });
  await expect(
    page.getByRole("heading", { name: "Job analysis" }),
  ).toBeVisible();
  await expect(page.getByText("What went wrong")).toHaveCount(0);
  await expect(page.locator("dl.runs__totals")).toContainText("2");
});

// ------------------------------------------------------------------ accessibility

const PAGES: {
  name: string;
  path: string;
  mock?: Mock;
  ready: (page: Page) => Promise<void>;
}[] = [
  {
    name: "health, critical",
    path: "/admin",
    mock: { health: TROUBLED },
    ready: (p) => expect(p.getByRole("list", { name: "Alerts" })).toBeVisible(),
  },
  {
    name: "health, healthy",
    path: "/admin",
    ready: (p) =>
      expect(p.getByText("Nothing. Every rule is quiet.")).toBeVisible(),
  },
  {
    name: "cost and usage",
    path: "/admin/usage",
    ready: (p) =>
      expect(p.getByRole("table", { name: /by model/ })).toBeVisible(),
  },
  {
    name: "a traced run",
    path: `/admin/runs?run=${RUN}`,
    ready: (p) =>
      expect(
        p.getByRole("table", { name: "Queue tasks for this run" }),
      ).toBeVisible(),
  },
  {
    name: "sources",
    path: "/admin/sources",
    ready: (p) =>
      expect(p.getByRole("table", { name: "Job sources" })).toBeVisible(),
  },
  {
    name: "a failed run",
    path: `/runs/${RUN}`,
    ready: (p) => expect(p.getByText("What to do:")).toBeVisible(),
  },
];

for (const theme of ["light", "dark"] as const) {
  for (const entry of PAGES) {
    test(`axe: ${entry.name} (${theme})`, async ({ page }) => {
      await page.addInitScript(
        (value) => window.localStorage.setItem("pv-theme", value),
        theme,
      );
      await open(page, entry.path, entry.mock);
      await entry.ready(page);
      await axe(page);
    });
  }
}

test("axe: the thresholds and the recent fetches when opened", async ({
  page,
}) => {
  await open(page, "/admin", { health: TROUBLED });
  await page.getByText("How these alerts are decided").click();
  await axe(page);
  await page.goto("/admin/sources");
  await page
    .getByRole("button", { name: /Recent fetches for Greenhouse/ })
    .click();
  await expect(
    page.getByRole("table", { name: "Recent fetches, newest first" }),
  ).toBeVisible();
  await axe(page);
});

test("on a phone the console and the run page do not scroll sideways", async ({
  page,
}) => {
  await open(page, "/admin", { health: TROUBLED });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("list", { name: "Alerts" })).toBeVisible();
  const wide = () =>
    page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
  expect(await wide()).toBeLessThanOrEqual(0);
  await page.goto(`/runs/${RUN}`);
  await expect(page.getByText("What to do:")).toBeVisible();
  expect(await wide()).toBeLessThanOrEqual(0);
});
