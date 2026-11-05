// A small fake of the plan and usage API, so the plan section is exercised with every meter state.

export interface FakePlan {
  plan_id: string;
  used: Record<string, number>;
  limits: Record<string, number | null>;
  resumes_used: number;
  recent: boolean;
}

export const newPlan = (over: Partial<FakePlan> = {}): FakePlan => ({
  plan_id: "free",
  used: {
    discovery_run: 2,
    job_analysis: 12,
    url_analysis: 0,
    material_generation: 3,
  },
  limits: {
    discovery_run: 20,
    job_analysis: 30,
    url_analysis: 15,
    material_generation: 20,
  },
  resumes_used: 1,
  recent: true,
  ...over,
});

const LABELS: Record<string, [string, string, string]> = {
  discovery_run: [
    "Job searches by sentence",
    "searches",
    "Each time you describe a search in a sentence and we turn it into a plan.",
  ],
  job_analysis: [
    "Job evidence checks",
    "checks",
    "Checking a job against your evidence. Checking the same job again in the same month is free.",
  ],
  url_analysis: [
    "Jobs read from an address",
    "jobs",
    "Reading a job from an address you give us.",
  ],
  material_generation: [
    "Pieces of written material",
    "pieces",
    "Resume tailoring suggestions, application drafts, and interview preparation material.",
  ],
};

export function planBody(p: FakePlan) {
  const state = (limit: number | null, used: number) =>
    limit === null
      ? "ok"
      : limit === 0 || used >= limit
        ? "reached"
        : used * 5 >= limit * 4
          ? "near"
          : "ok";
  return {
    plan_id: p.plan_id,
    plan_label:
      p.plan_id === "free" ? "Free" : p.plan_id === "pro" ? "Pro" : "Starter",
    period_start: "2026-11-01",
    resets_at: "2026-12-01T00:00:00+00:00",
    quotas: Object.keys(LABELS).map((unit) => {
      const limit = p.limits[unit] ?? null;
      const used = p.used[unit] ?? 0;
      return {
        unit,
        label: LABELS[unit]![0],
        noun: LABELS[unit]![1],
        help: LABELS[unit]![2],
        used,
        limit,
        remaining: limit === null ? null : Math.max(0, limit - used),
        percent:
          limit === null
            ? 0
            : limit === 0
              ? 100
              : Math.min(100, Math.round((100 * used) / limit)),
        state: state(limit, used),
      };
    }),
    resumes_used: p.resumes_used,
    resumes_limit: 1,
    exports_per_resume: 5,
    plans: [
      {
        id: "free",
        label: "Free",
        current: p.plan_id === "free",
        limits: {
          discovery_run: 20,
          job_analysis: 30,
          url_analysis: 15,
          material_generation: 20,
        },
        resumes: 1,
        exports_per_resume: 5,
      },
      {
        id: "starter",
        label: "Starter",
        current: p.plan_id === "starter",
        limits: {
          discovery_run: 100,
          job_analysis: 150,
          url_analysis: 75,
          material_generation: 100,
        },
        resumes: 3,
        exports_per_resume: 20,
      },
      {
        id: "pro",
        label: "Pro",
        current: p.plan_id === "pro",
        limits: {
          discovery_run: 500,
          job_analysis: 800,
          url_analysis: 300,
          material_generation: 500,
        },
        resumes: 10,
        exports_per_resume: 50,
      },
    ],
    recent: p.recent
      ? [
          {
            label: "Job evidence checks",
            amount: 1,
            at: "2026-11-04T09:30:00Z",
          },
          {
            label: "Pieces of written material",
            amount: 1,
            at: "2026-11-03T16:00:00Z",
          },
        ]
      : [],
    payments: {
      enabled: false,
      message:
        "Paid plans are not available yet. Nothing is charged and nothing is collected. The limits on your plan are shown below.",
    },
    provisional: true,
  };
}
