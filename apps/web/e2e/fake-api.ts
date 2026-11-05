// A small stateful fake of the API for browser tests of the profile screen.
import { resolve } from "node:path";
import type { Page, Route } from "@playwright/test";

export const NOW = "2026-10-30T09:00:00Z";
export const USER = {
  id: "11111111-1111-4111-8111-111111111111",
  email: "asha@example.com",
  role: "USER",
  email_verified: true,
};

export const field = (
  name: string,
  label: string,
  kind: string,
  required = false,
  recommended = false,
  hint = "",
) => ({
  name,
  label,
  kind,
  max_length: 200,
  required,
  recommended,
  hint,
});
export const SPECS = [
  {
    entry_type: "education",
    label: "Education",
    plural: "Education",
    primary_field: "institution",
    fields: [
      field("institution", "Institution", "text", true),
      field("degree", "Degree", "text", false, true),
      field(
        "end_date",
        "End or expected end",
        "date",
        false,
        true,
        "YYYY or YYYY-MM",
      ),
    ],
  },
  {
    entry_type: "work",
    label: "Work experience",
    plural: "Work experience",
    primary_field: "company",
    fields: [
      field("company", "Company", "text", true),
      field("title", "Role", "text", true),
      field("start_date", "Start", "date", false, true, "YYYY or YYYY-MM"),
      field(
        "highlights",
        "What you did",
        "list",
        false,
        true,
        "One achievement per line.",
      ),
    ],
  },
  {
    entry_type: "skill",
    label: "Skill",
    plural: "Skills",
    primary_field: "name",
    fields: [
      field("name", "Skill", "text", true),
      field("category", "Group", "text"),
    ],
  },
  {
    entry_type: "project",
    label: "Project",
    plural: "Projects",
    primary_field: "name",
    fields: [
      field("name", "Project name", "text", true),
      field("description", "What it is", "longtext", false, true),
      field("url", "Link", "url"),
    ],
  },
];

export interface Entry {
  id: string;
  entry_type: string;
  data: Record<string, unknown>;
  user_edited: boolean;
  source: "resume" | "user" | "github";
  flags: string[];
  created_at: string;
  updated_at: string;
}

export function flagsFor(
  type: string,
  data: Record<string, unknown>,
): string[] {
  const spec = SPECS.find((s) => s.entry_type === type);
  return (spec?.fields ?? [])
    .filter((f) => f.recommended && !data[f.name])
    .map((f) => f.name);
}

export function makeEntry(
  id: string,
  type: string,
  data: Record<string, unknown>,
  source: "resume" | "user" = "resume",
): Entry {
  return {
    id,
    entry_type: type,
    data,
    user_edited: false,
    source,
    flags: flagsFor(type, data),
    created_at: NOW,
    updated_at: NOW,
  };
}

export const PARSED_ENTRIES = (): Entry[] => [
  makeEntry("e1", "education", {
    institution: "BMS College of Engineering",
    degree: "B.E.",
    end_date: "2025",
  }),
  makeEntry("e2", "work", {
    company: "Kestrel Analytics",
    title: "Data Intern",
  }),
  makeEntry("e3", "skill", { name: "Python" }),
];

export function resumeBody(
  uiState: string,
  extra: Record<string, unknown> = {},
) {
  return {
    id: "r1",
    original_filename: "Asha CV.pdf",
    file_kind: "pdf",
    size_bytes: 52000,
    ui_state: uiState,
    can_retry:
      uiState === "parsed" ||
      uiState === "needs_correction" ||
      uiState === "confirmed" ||
      uiState === "failed",
    error_message: null,
    kept_entry_count: 3,
    dropped_entry_count: 1,
    flagged_entry_count: 2,
    page_count: 1,
    run_id: "run1",
    created_at: NOW,
    parsed_at: uiState === "uploaded" || uiState === "parsing" ? null : NOW,
    confirmed_at: uiState === "confirmed" ? NOW : null,
    ...extra,
  };
}

export interface FakeJob {
  id: string;
  text: string;
  source: string;
  url: string | null;
  state: "reading" | "ready" | "failed";
  /** Workbench fields. Left out, a ready job looks like the sample data analyst posting. */
  title?: string;
  company?: string;
  mode?: string;
  place?: string;
  elig?: string;
  band?: string | null;
  dstate?: string;
  note?: string;
  appliedAt?: string | null;
  added?: string;
  acquisition?: string;
}

const OFFER: Record<string, string[]> = {
  new: ["save", "approve", "mark_applied", "dismiss"],
  saved: ["unsave", "approve", "mark_applied", "dismiss"],
  approved_for_prep: ["mark_applied", "dismiss"],
  dismissed: ["undo_dismiss", "archive"],
  applied: ["undo_applied", "archive"],
  archived: [],
};
const ACTION_LABEL: Record<string, string> = {
  save: "Save",
  unsave: "Unsave",
  dismiss: "Dismiss",
  undo_dismiss: "Undo dismiss",
  approve: "Approve for preparation",
  mark_applied: "Mark applied",
  undo_applied: "Undo applied",
  archive: "Archive",
};
const STATE_LABEL: Record<string, string> = {
  new: "New",
  saved: "Saved",
  dismissed: "Dismissed",
  approved_for_prep: "Approved for preparation",
  applied: "Applied",
  archived: "Archived",
};
const TARGET: Record<string, string> = {
  save: "saved",
  unsave: "new",
  dismiss: "dismissed",
  undo_dismiss: "new",
  approve: "approved_for_prep",
  mark_applied: "applied",
  undo_applied: "new",
  archive: "archived",
};
const REVERSE: Record<string, string> = {
  save: "unsave",
  dismiss: "undo_dismiss",
  mark_applied: "undo_applied",
};
const VIEW_STATES: Record<string, string[]> = {
  active: ["new", "saved", "approved_for_prep"],
  saved: ["saved", "approved_for_prep"],
  applications: ["applied"],
  dismissed: ["dismissed"],
  archived: ["archived"],
  all: [
    "new",
    "saved",
    "dismissed",
    "approved_for_prep",
    "applied",
    "archived",
  ],
};

export function decisionBody(job: FakeJob) {
  const state = job.dstate ?? "new";
  const eligible = (job.elig ?? "requires_user_input") !== "not_eligible";
  return {
    state,
    state_label: STATE_LABEL[state],
    actions: (OFFER[state] ?? [])
      .filter((a) => a !== "approve" || eligible)
      .map((a) => ({ action: a, label: ACTION_LABEL[a] })),
    note: job.note ?? "",
    applied_at: job.appliedAt ?? null,
    updated_at: null,
  };
}

/** The same rules as the server, so the screens can be driven without it. Returns a refusal or null. */
export function moveJob(job: FakeJob, action: string): string | null {
  const state = job.dstate ?? "new";
  if (!(OFFER[state] ?? []).includes(action))
    return `${ACTION_LABEL[action] ?? action} is not available for a job that is ${(STATE_LABEL[state] ?? state).toLowerCase()}.`;
  if (action === "approve" && (job.elig ?? "") === "not_eligible")
    return "A hard requirement stands in the way of this job, so it cannot be approved for preparation. You can still save it or dismiss it.";
  job.dstate = TARGET[action];
  job.appliedAt =
    action === "mark_applied"
      ? NOW
      : action === "undo_applied"
        ? null
        : (job.appliedAt ?? null);
  return null;
}

export function workRow(job: FakeJob) {
  const ready = job.state === "ready";
  return {
    id: job.id,
    title: job.title ?? (ready ? "Data Analyst, Early Careers" : null),
    company: job.company ?? (ready ? "Fernlight Systems" : null),
    source_name: job.source,
    acquisition_method: job.acquisition ?? "user_paste",
    work_mode: ready ? (job.mode ?? "hybrid") : null,
    location: ready ? (job.place ?? "Bengaluru, India") : null,
    employment_type: ready ? "full_time" : null,
    seniority: ready ? "entry" : null,
    eligibility: ready ? (job.elig ?? "requires_user_input") : null,
    band: ready ? (job.band ?? null) : null,
    reading: job.state,
    decision: decisionBody(job),
    has_note: Boolean(job.note),
    created_at: job.added ?? NOW,
  };
}

const POSTING_TEXT = [
  "Data Analyst, Early Careers",
  "Fernlight Systems | Bengaluru, India (Hybrid) | Full time",
  "",
  "You will write SQL to answer questions from product teams. Strong SQL and Python (pandas).",
  "0-2 years of experience. Must be authorized to work in India.",
].join("\n");

export function jobBody(job: FakeJob) {
  const ready = job.state === "ready";
  return {
    id: job.id,
    title: job.title ?? (ready ? "Data Analyst, Early Careers" : null),
    company: job.company ?? (ready ? "Fernlight Systems" : null),
    decision: decisionBody(job),
    source_name: job.source,
    acquisition_method: job.acquisition ?? "user_paste",
    ui_state: job.state,
    can_retry: job.state !== "reading",
    error_message:
      job.state === "failed"
        ? "The reading service did not answer. Your posting is saved. Try again in a few minutes."
        : null,
    eligibility: ready ? (job.elig ?? "requires_user_input") : null,
    work_mode: ready ? (job.mode ?? "hybrid") : null,
    location: ready ? (job.place ?? "Bengaluru, India") : null,
    requirement_count: ready ? 2 : 0,
    created_at: NOW,
    source_url: job.url,
    visibility: "private",
    facts: ready
      ? {
          work_mode: { value: "hybrid", quote: "Bengaluru, India (Hybrid)" },
          location: {
            value: "Bengaluru, India",
            quote: "Bengaluru, India (Hybrid)",
          },
          min_years_experience: { value: 2, quote: "0-2 years of experience" },
          work_authorization_countries: {
            value: ["India"],
            quote: "Must be authorized to work in India.",
          },
        }
      : {},
    requirements: ready
      ? [
          {
            id: "q1",
            ordinal: 0,
            text: "Write SQL to answer product questions",
            kind: "required",
            category: "skill",
            years_min: null,
            quote: "write SQL to answer questions from product teams",
            quote_start: 100,
            quote_end: 150,
          },
          {
            id: "q2",
            ordinal: 1,
            text: "Experience with Tableau",
            kind: "preferred",
            category: "skill",
            years_min: null,
            quote: "experience with Tableau",
            quote_start: 160,
            quote_end: 183,
          },
        ]
      : [],
    eligibility_detail: ready
      ? {
          state: "requires_user_input",
          rules_version: "eligibility-1",
          gates: [
            {
              gate: "authorization",
              label: "Work authorization and sponsorship",
              state: "requires_user_input",
              reason:
                "The posting requires permission to work in india. Add the countries where you can work without a visa in your preferences.",
              posting_quote: "Must be authorized to work in India.",
            },
            {
              gate: "location",
              label: "Location and work mode",
              state: "uncertain",
              reason:
                "The role is hybrid in Bengaluru, India, a place you listed. You said you prefer remote work, so review it.",
              posting_quote: "Bengaluru, India (Hybrid)",
            },
            {
              gate: "seniority",
              label: "Experience asked for",
              state: "eligible",
              reason:
                "The posting asks for 2 years. Your profile shows about 1.",
              posting_quote: "0-2 years of experience",
            },
            {
              gate: "employment",
              label: "Kind of work",
              state: "eligible",
              reason: "You have not limited the kind of work.",
              posting_quote: null,
            },
            {
              gate: "exclusions",
              label: "Things you chose to avoid",
              state: "eligible",
              reason: "You have not listed anything to avoid.",
              posting_quote: null,
            },
          ],
        }
      : null,
    facts_dropped: ready ? 1 : 0,
    requirements_dropped: ready ? 1 : 0,
    prompt_version: "job-extract-1",
    run_id: "run-job",
    extracted_at: ready ? NOW : null,
    text: job.text,
  };
}

export interface FakeAnalysis {
  state: "working" | "needs_answer" | "ready" | "failed";
  reads: number;
  /** What the check ends in once it has run: a finished result, a question, or a failure. */
  ends: "ready" | "needs_answer" | "failed";
  answered: boolean;
  feedback: Record<string, "right" | "wrong">;
  blocker: string | null;
}

const CITE_SQL = {
  chunk_id: "c1",
  quote: "Skill: SQL",
  source: "profile",
  entry_type: "skill",
  changed: false,
};
const CITE_STATS = {
  chunk_id: "c2",
  quote: "ran hypothesis tests on churn",
  source: "profile",
  entry_type: "internship",
  changed: false,
};
const CITE_ANSWER = {
  chunk_id: "c3",
  quote: "built three Power BI dashboards",
  source: "answer",
  entry_type: null,
  changed: false,
};

function verdictRow(
  id: string,
  requirement: string,
  kind: "required" | "preferred",
  verdict: string | null,
  extra: Record<string, unknown>,
  fb: FakeAnalysis,
) {
  return {
    requirement_id: id,
    requirement,
    kind,
    category: "skill",
    posting_quote: requirement,
    verdict,
    evidence_kind: null,
    confidence: verdict ? "none" : null,
    citations: [],
    reason: "",
    capped: false,
    feedback: fb.feedback[id] ?? null,
    ...extra,
  };
}

export function analysisBody(a: FakeAnalysis | undefined) {
  if (!a) {
    return {
      ui_state: "not_started",
      can_start: true,
      blocker: null,
      error_message: null,
      checked: 0,
      total: 4,
      score: null,
      verdicts: [
        "Write SQL to answer product questions",
        "Build dashboards in a BI tool",
        "Statistics including hypothesis testing",
      ]
        .map((t, i) =>
          verdictRow(`r${i}`, t, "required", null, {}, {
            feedback: {},
          } as FakeAnalysis),
        )
        .concat([
          verdictRow("r3", "Experience with Tableau", "preferred", null, {}, {
            feedback: {},
          } as FakeAnalysis),
        ]),
      gate_requirements: [
        {
          requirement_id: "g1",
          requirement: "Authorized to work in India",
          kind: "required",
        },
      ],
      questions: [],
      gaps: [],
      stale: false,
      recommendation_feedback: null,
      scoring_version: "scoring-1",
      prompt_version: null,
    };
  }
  const done = a.state === "ready";
  const asking = a.state === "needs_answer";
  const dash = a.answered
    ? verdictRow(
        "r1",
        "Build dashboards in a BI tool",
        "required",
        "met",
        {
          evidence_kind: "direct",
          confidence: "high",
          citations: [CITE_ANSWER],
          reason: "You describe building dashboards.",
        },
        a,
      )
    : verdictRow(
        "r1",
        "Build dashboards in a BI tool",
        "required",
        asking || a.state === "working" ? null : "not_verified",
        { reason: "Nothing in your profile supports this yet." },
        a,
      );
  const verdicts = [
    verdictRow(
      "r0",
      "Write SQL to answer product questions",
      "required",
      "met",
      {
        evidence_kind: "direct",
        confidence: "high",
        citations: [CITE_SQL],
        reason: "Your skills list names SQL.",
      },
      a,
    ),
    dash,
    verdictRow(
      "r2",
      "Statistics including hypothesis testing",
      "required",
      "partial",
      {
        evidence_kind: "direct",
        confidence: "medium",
        citations: [CITE_STATS],
        reason: "One internship task used hypothesis tests.",
      },
      a,
    ),
    verdictRow(
      "r3",
      "Experience with Tableau",
      "preferred",
      a.state === "working" ? null : "not_verified",
      { reason: "Nothing in your profile supports this yet." },
      a,
    ),
  ];
  const met = a.answered ? 2 : 1;
  const failed = a.state === "failed";
  return {
    ui_state: a.state === "needs_answer" ? "needs_answer" : a.state,
    can_start: !["working", "needs_answer"].includes(a.state),
    blocker: a.blocker,
    error_message: failed
      ? "The checking service did not answer. Your results so far are saved. Check again in a few minutes and it continues where it stopped."
      : null,
    checked: verdicts.filter((v) => v.verdict).length,
    total: 4,
    score: done
      ? {
          scoring_version: "scoring-1",
          band: a.answered ? "good" : "review",
          required_total: 3,
          met,
          partial: 1,
          conflicting: 0,
          not_verified: a.answered ? 0 : 1,
          preferred_total: 1,
          preferred_supported: 0,
          reasons: [
            `${met + 1} of 3 required requirements supported (${met} fully, 1 partly).`,
            "Nice to have: 0 of 1 supported. These never lower the band.",
            "Eligibility: it needs an answer from you. See the checks above.",
          ],
        }
      : null,
    verdicts,
    gate_requirements: [
      {
        requirement_id: "g1",
        requirement: "Authorized to work in India",
        kind: "required",
      },
    ],
    questions:
      asking || a.answered
        ? [
            {
              id: "q1",
              requirement_id: "r1",
              requirement: "Build dashboards in a BI tool",
              question: "Have you built dashboards in a course or project?",
              status: a.answered ? "answered" : "pending",
              answer: a.answered ? "I built three Power BI dashboards." : null,
            },
          ]
        : [],
    gaps:
      done && !a.answered
        ? [
            {
              requirement_id: "r1",
              requirement: "Build dashboards in a BI tool",
              state: "not_verified",
              proof_needed: "An entry that shows you using it.",
              next_step:
                "Add a project or experience entry that says what you built with it.",
            },
          ]
        : [],
    stale: false,
    recommendation_feedback: a.feedback["rec"] ?? null,
    scoring_version: "scoring-1",
    prompt_version: "evidence-agent-1",
  };
}

export interface FakeStudio {
  doc: Record<string, any> | null;
  versions: { id: string; revision: number; created_at: string }[];
  exportReads: number;
  exportState: "none" | "preparing" | "ready" | "failed";
  /** Set to make the next save fail the way a stale tab does. */
  conflict: boolean;
  saves: Record<string, any>[];
  /** Jobs whose evidence check is finished, so a resume can be tailored to them. */
  tailorJobs: {
    job_id: string;
    title: string | null;
    company: string | null;
  }[];
  /** The tailoring run once started: it reads as working twice, then ready. */
  tailoring: Record<string, any> | null;
  tailorReads: number;
  /** What the fake model suggests when asked. */
  tailorSuggestions: Record<string, any>[];
}

export function newStudio(): FakeStudio {
  return {
    doc: null,
    versions: [],
    exportReads: 0,
    exportState: "none",
    conflict: false,
    saves: [],
    tailorJobs: [],
    tailoring: null,
    tailorReads: 0,
    tailorSuggestions: [],
  };
}

export const STUDIO_OPTIONS = {
  templates: [
    {
      key: "classic",
      name: "Classic",
      description: "A serif name and headings over plain body text.",
      ats_safe: true,
    },
    {
      key: "modern",
      name: "Modern",
      description: "Sans serif with an accent color.",
      ats_safe: true,
    },
    {
      key: "compact",
      name: "Compact",
      description: "Tighter type and spacing.",
      ats_safe: true,
    },
  ],
  font_pairs: [
    { key: "plex-newsreader", label: "Serif headings, sans body" },
    { key: "plex", label: "Sans serif throughout" },
    { key: "newsreader", label: "Serif throughout" },
    { key: "inter", label: "Inter throughout" },
    { key: "inter-lora", label: "Lora headings, Inter body" },
    { key: "lato", label: "Lato throughout" },
    { key: "montserrat-lato", label: "Montserrat headings, Lato body" },
    { key: "source", label: "Source Sans throughout" },
    {
      key: "source-merriweather",
      label: "Merriweather headings, Source Sans body",
    },
    { key: "playfair-source", label: "Playfair headings, Source Sans body" },
    { key: "lora", label: "Lora throughout" },
    { key: "merriweather", label: "Merriweather throughout" },
  ],
  sizes: ["small", "medium", "large"],
  spacings: ["tight", "normal", "relaxed"],
  margins: ["narrow", "normal", "wide"],
  dividers: ["none", "thin", "bold", "dotted"],
  papers: ["a4", "letter"],
  section_kinds: [
    "summary",
    "experience",
    "education",
    "projects",
    "skills",
    "certifications",
    "achievements",
    "custom",
  ],
  max_resumes: 1,
};

export const SEARCH_SOURCES = [
  {
    key: "lever",
    display_name: "Lever postings",
    source_type: "ats_board",
    outcome: "unavailable",
    message:
      "Lever postings is currently unavailable. Reason: It is switched off. You can still import jobs you collected from Lever postings.",
    reason: "It is switched off.",
    import_available: true,
    compliance_status: "verified",
    terms_checked_at: "2026-11-02",
    terms_url: "https://www.lever.co/terms-of-service/",
    attribution_text: "",
    health_status: "healthy",
    last_success_at: "2026-11-02T10:00:00Z",
    jobs_open: 2,
  },
  {
    key: "linkedin",
    display_name: "LinkedIn",
    source_type: "user_import_only",
    outcome: "import_required",
    message:
      "Automated search for LinkedIn is not available. Import jobs by URL, paste, or CSV/XLSX and we will analyze them.",
    reason:
      "Automated access to this platform is not permitted, so jobs from it are imported by you.",
    import_available: true,
    compliance_status: "prohibited",
    terms_checked_at: "2026-11-02",
    terms_url: "https://www.linkedin.com/legal/user-agreement",
    attribution_text: "",
    health_status: "unknown",
    last_success_at: null,
    jobs_open: 0,
  },
];

export interface FakeMatch {
  group_id: string;
  state: string;
  auto: boolean;
  title: string;
  reason: string;
  sightings: any[];
}

const SIGHT = (name: string, url: string) => ({
  kind: "public",
  source_name: name,
  board_id: "acme",
  title: "Data Engineer",
  location: "London, UK",
  url,
  first_seen_at: "2026-11-01T09:00:00Z",
  last_seen_at: "2026-11-04T09:00:00Z",
  seen_count: 4,
  closed: false,
  how: "Published by " + name,
});

export const SAMPLE_MATCHES: FakeMatch[] = [
  {
    group_id: "g1",
    state: "auto",
    auto: true,
    title: "Data Engineer",
    reason: "Same company, title and place, and 92% of the wording matches.",
    sightings: [
      SIGHT("Lever postings", "https://jobs.lever.co/acme/1"),
      SIGHT("Greenhouse job boards", "https://boards.greenhouse.io/acme/9"),
    ],
  },
  {
    group_id: "g2",
    state: "suggested",
    auto: false,
    title: "Analytics Engineer",
    reason: "A close title in the same place, and 71% of the wording matches.",
    sightings: [SIGHT("Lever postings", "https://jobs.lever.co/acme/2")],
  },
];

export function matchesBody(fake: { matches: FakeMatch[] }) {
  const linked = fake.matches.filter(
    (m) => m.state === "auto" || m.state === "confirmed",
  );
  return {
    note:
      fake.matches.length === 0
        ? "No matching posting was found among the jobs fetched from permitted sources. That does not mean it is not posted elsewhere."
        : null,
    sightings: [
      {
        kind: "yours",
        source_name: "Wellfound",
        board_id: null,
        title: "Data Engineer",
        location: "",
        url: null,
        first_seen_at: "2026-11-03T09:00:00Z",
        last_seen_at: "2026-11-03T09:00:00Z",
        seen_count: 1,
        closed: false,
        how: "Pasted by you",
      },
      ...linked.flatMap((m) => m.sightings),
    ],
    matches: fake.matches.map((m) => ({
      group_id: m.group_id,
      title: m.title,
      company_name: "Acme",
      location: "London, UK",
      source_name: "Lever postings",
      url: "https://jobs.lever.co/acme/1",
      method: "same_company_title_place",
      score: 0.9,
      reason: m.reason,
      state: m.state,
      sightings: m.sightings,
    })),
  };
}

export const FETCHED_JOBS = [
  {
    id: "j1",
    title: "Backend Engineer",
    company_name: "Palantir",
    location: "London, United Kingdom",
    workplace: "hybrid",
    employment_type: "full_time",
    department: "Engineering",
    url: "https://jobs.lever.co/palantir/1",
    excerpt: "Build data systems used by governments and companies.",
    source_key: "lever",
    source_name: "Lever postings",
    attribution_text: "",
    posted_at: "2026-11-01T09:00:00Z",
    first_seen_at: "2026-11-02T10:00:00Z",
    also_seen: [
      {
        kind: "public",
        source_name: "Greenhouse job boards",
        board_id: "palantir",
        title: "Backend Engineer",
        location: "London",
        url: "https://boards.greenhouse.io/palantir/9",
        first_seen_at: "2026-11-02T10:00:00Z",
        last_seen_at: "2026-11-04T10:00:00Z",
        seen_count: 3,
        closed: false,
        how: "Published by Greenhouse job boards",
      },
    ],
  },
  {
    id: "j2",
    title: "Data Analyst",
    company_name: "Palantir",
    location: "Remote",
    workplace: "remote",
    employment_type: "full_time",
    department: "Analytics",
    url: "https://jobs.lever.co/palantir/2",
    excerpt: "",
    source_key: "lever",
    source_name: "Lever postings",
    attribution_text: "",
    posted_at: null,
    first_seen_at: "2026-11-02T10:00:00Z",
    also_seen: [],
  },
];

export function searchPlan(body: {
  query?: string;
  intent?: Record<string, any>;
}) {
  const intent = body.intent ?? {};
  if (body.query?.includes("searchable")) {
    return {
      interpreted_by: "the AI service",
      intent: {
        roles: ["Backend Engineer"],
        skills: [],
        min_years: null,
        max_years: null,
        locations: [],
        work_mode: "any",
        employment_types: [],
        compensation: null,
        companies: ["Palantir"],
        sources: ["all_permitted"],
        exclusions: [],
      },
      headline: "Searching Lever postings.",
      can_search_now: true,
      notes: [],
      sources: [
        {
          key: "lever",
          display_name: "Lever postings",
          outcome: "search",
          message: "Searching Lever postings",
          reason: null,
          import_available: true,
          named_by_person: false,
          notes: [],
        },
      ],
      companies: [
        {
          query: "Palantir",
          status: "resolved",
          route: "first_party",
          message: "Using the company's own career system (Lever postings).",
          company: { key: "palantir", name: "Palantir", score: 1 },
          source_key: "lever",
          candidates: [],
        },
      ],
      authorization: {
        countries: ["India"],
        needs_sponsorship: false,
        origin: "your profile",
      },
    };
  }
  const companies: string[] =
    intent.companies ??
    (body.query?.includes("Google")
      ? ["Google"]
      : body.query?.includes("Tata")
        ? ["Tata"]
        : []);
  return {
    interpreted_by:
      body.query !== undefined ? "the AI service" : "the fields you set",
    intent: {
      roles: intent.roles ?? ["Backend Engineer"],
      skills: [],
      min_years: null,
      max_years: null,
      locations: intent.locations ?? ["India"],
      work_mode: intent.work_mode ?? "any",
      employment_types: [],
      compensation: null,
      companies,
      sources: ["all_permitted"],
      exclusions: [],
    },
    headline:
      "No source can be searched automatically for this yet. You can import jobs and we will analyze them.",
    can_search_now: false,
    notes: [],
    sources: [
      {
        key: "linkedin",
        display_name: "LinkedIn",
        outcome: "import_required",
        message: SEARCH_SOURCES[1]!.message,
        reason: SEARCH_SOURCES[1]!.reason,
        import_available: true,
        named_by_person: false,
        notes: [],
      },
      {
        key: "lever",
        display_name: "Lever postings",
        outcome: "unavailable",
        message: SEARCH_SOURCES[0]!.message,
        reason: "It is switched off.",
        import_available: true,
        named_by_person: false,
        notes: [],
      },
    ],
    companies: companies.map((q) =>
      q === "Tata"
        ? {
            query: q,
            status: "ambiguous",
            route: "choose",
            message:
              "Which one did you mean by Tata? Tata Consultancy Services, Tata Motors.",
            company: null,
            source_key: null,
            candidates: [
              { key: "tcs", name: "Tata Consultancy Services", score: 0.8 },
              { key: "tata-motors", name: "Tata Motors", score: 0.8 },
            ],
          }
        : {
            query: q,
            status: "resolved",
            route: "import",
            message:
              "No permitted source can be searched for " +
              q +
              ". Import jobs by URL, paste, or CSV/XLSX and we will analyze them.",
            company: { key: q.toLowerCase(), name: q, score: 1 },
            source_key: null,
            candidates: [],
          },
    ),
    authorization: {
      countries: ["India"],
      needs_sponsorship: false,
      origin: "your profile",
    },
  };
}

export function studioContent(template = "classic", name = "") {
  return {
    version: 1,
    style: {
      template,
      font_pair: "plex-newsreader",
      size: "medium",
      spacing: "normal",
      margins: "normal",
      accent: "#222222",
      divider: "thin",
      paper: "a4",
    },
    header: { name, headline: "", contacts: [] },
    sections: [
      {
        id: "s1",
        kind: "experience",
        title: "Experience",
        blocks: [
          {
            id: "b1",
            heading: "Data Intern",
            subheading: "Kestrel Analytics",
            dates: "2025-06 to 2025-08",
            location: "",
            body: {
              type: "doc",
              content: [
                {
                  type: "bulletList",
                  content: [
                    {
                      type: "listItem",
                      content: [
                        {
                          type: "paragraph",
                          content: [
                            {
                              type: "text",
                              text: "Cleaned six CSV sources with pandas",
                            },
                          ],
                        },
                      ],
                    },
                  ],
                },
              ],
            },
          },
        ],
      },
      {
        id: "s2",
        kind: "education",
        title: "Education",
        blocks: [
          {
            id: "b2",
            heading: "B.E. Computer Science",
            subheading: "BMS College of Engineering",
            dates: "2026",
            location: "",
            body: null,
          },
        ],
      },
    ],
  };
}

export function studioDoc(
  name = "Asha Rao",
  template = "classic",
  revision = 1,
) {
  return {
    id: "doc-1",
    title: "My resume",
    revision,
    template,
    updated_at: NOW,
    content: studioContent(template, name),
  };
}

function para(text: string, marks: string[] = []) {
  return {
    type: "paragraph",
    content: [
      {
        type: "text",
        text,
        ...(marks.length ? { marks: marks.map((type) => ({ type })) } : {}),
      },
    ],
  };
}

function textEl(
  id: string,
  name: string,
  x: number,
  y: number,
  w: number,
  h: number,
  body: unknown,
  extra: Record<string, unknown> = {},
) {
  return {
    id,
    kind: "text",
    name,
    x,
    y,
    w,
    h,
    locked: false,
    group: null,
    body,
    font: "body",
    size: 10.5,
    color: "ink",
    align: "left",
    line_height: 1.3,
    caps: false,
    ...extra,
  };
}

/** A free canvas resume: a name, a headline, a rule, a role with a right-aligned date, and bullets. */
export function canvasContent(name = "Asha Rao") {
  const bullets = {
    type: "doc",
    content: [
      {
        type: "bulletList",
        content: [
          "Cleaned six CSV sources with pandas",
          "Wrote SQL joins over 1.2 million rows",
        ].map((line) => ({ type: "listItem", content: [para(line)] })),
      },
    ],
  };
  return {
    version: 2,
    style: {
      template: "classic",
      font_pair: "plex-newsreader",
      accent: "#1f3d7a",
      ink: "#1b1b1b",
      muted: "#4a4a4a",
      tint: "#eef1f6",
      paper: "a4",
      margin_mm: 16,
    },
    pages: [
      {
        id: "pg1",
        elements: [
          textEl(
            "name",
            "Name",
            16,
            16,
            178,
            11,
            { type: "doc", content: [para(name)] },
            { font: "heading", size: 26, color: "accent", line_height: 1.1 },
          ),
          textEl(
            "headline",
            "Headline",
            16,
            29,
            178,
            6,
            { type: "doc", content: [para("Data analyst")] },
            { size: 11 },
          ),
          {
            id: "rule",
            kind: "shape",
            name: "Rule",
            x: 16,
            y: 38,
            w: 178,
            h: 0.4,
            locked: false,
            group: null,
            fill: "accent",
            stroke: "none",
            stroke_pt: 0,
            radius: 0,
          },
          textEl("role", "Role", 16, 44, 140, 6, {
            type: "doc",
            content: [para("Data Intern, Kestrel Analytics", ["bold"])],
          }),
          textEl(
            "dates",
            "Dates",
            158,
            44,
            36,
            5,
            { type: "doc", content: [para("2025-06 to 2025-08")] },
            { align: "right", size: 9.5, color: "muted" },
          ),
          textEl("bullets", "Highlights", 16, 52, 178, 12, bullets),
        ],
      },
    ],
  };
}

export function canvasDoc(name = "Asha Rao", revision = 1) {
  return {
    id: "doc-1",
    title: "My resume",
    revision,
    template: "classic",
    updated_at: NOW,
    content: canvasContent(name),
  };
}

export function previewHtml(content: any): string {
  const sections = (content.sections ?? [])
    .map((s: any) => `<h2>${s.title}</h2>`)
    .join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Resume</title><style>body{margin:0;background:#e9e9e6;font-family:sans-serif}.sheet{width:794px;min-height:1123px;margin:0 auto;padding:60px;box-sizing:border-box;background:#fff}</style></head><body><main class="sheet"><h1>${content.header?.name ?? ""}</h1>${sections}</main></body></html>`;
}

import { newPlan, planBody } from "./fake-plan";
import type { FakePlan } from "./fake-plan";
import { handlePreparation, newPrep } from "./fake-prep";
import type { FakePrep } from "./fake-prep";

export interface Fake {
  resume: ReturnType<typeof resumeBody> | null;
  entries: Entry[];
  reads: number;
  prefs: Record<string, unknown>;
  nextId: number;
  /** Whether the fake backend has an AI key and embedded entries. */
  meaning: "off" | "ready";
  jobs: FakeJob[];
  jobReads: Record<string, number>;
  analyses: Record<string, FakeAnalysis>;
  studio: FakeStudio;
  /** Public jobs that may be the pasted posting. */
  matches: FakeMatch[];
  /** Imports started in this session. Each one reads for two polls, then ends. */
  imports: FakeImport[];
  importReads: Record<string, number>;
  /** Saved views, and what the last workbench request asked for. */
  views: {
    id: string;
    name: string;
    query: Record<string, any>;
    created_at: string;
  }[];
  asked: string[];
  /** Pictures the person has uploaded. */
  images: FakeImage[];
  /** Saved themes. */
  themes: FakeTheme[];
  /** The GitHub connection. */
  github: FakeGitHub;
  /** Career preparation for the sample job. */
  prep: FakePrep;
  /** The person's plan and usage. */
  plan: FakePlan;
  /** Application drafts per job. Each is working for two reads, then ready. */
  drafts: Record<string, FakeDraft[]>;
  /** Whether the evidence check of every job is complete, so drafts can be written. */
  checked: boolean;
  /** The shortlist email: the person's settings, the runs, and whether the address is verified. */
  shortlist: {
    enabled: boolean;
    frequency: string;
    weekday: number;
    hour: number;
    timezone: string;
    max_items: number;
    next_run_at: string | null;
    last_run_at: string | null;
  };
  runs: {
    outcome: string;
    outcome_text: string;
    item_count: number;
    manual: boolean;
    at: string;
  }[];
  verified: boolean;
}

export interface FakeGitHubRepo {
  id: number;
  full_name: string;
  name: string;
  description: string;
  language: string;
  topics: string[];
  stars: number;
  fork: boolean;
  archived: boolean;
  url: string;
  selected: boolean;
  suggested: boolean;
  has_excerpt: boolean;
}
export interface FakeGitHub {
  available: boolean;
  connected: boolean;
  reads: number;
  sync_state: string;
  sync_error: string | null;
  repos: FakeGitHubRepo[];
  revoked: boolean;
  calls: string[];
}

export function githubRepos(): FakeGitHubRepo[] {
  return [1, 2, 3, 4].map((i) => ({
    id: i,
    full_name: `asha/project-${i}`,
    name: `project-${i}`,
    description: `Project ${i} loads data into a clean table`,
    language: "Python",
    topics: [],
    stars: i,
    fork: false,
    archived: false,
    url: `https://github.com/asha/project-${i}`,
    selected: false,
    suggested: i <= 2,
    has_excerpt: false,
  }));
}

export interface FakeTheme {
  id: string;
  name: string;
  font_pair: string;
  accent: string;
  ink: string;
  muted: string;
  tint: string;
  updated_at: string;
}

export interface FakeImage {
  id: string;
  name: string;
  width: number;
  height: number;
  used?: boolean;
}

// A 2 by 2 pixel PNG, so a picture can be shown without a real file.
export const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFklEQVR4nGP4z8Dwn4GBgQGM/zMAAB4OAwFQhU1LAAAAAElFTkSuQmCC",
  "base64",
);

export function imageBody(i: FakeImage) {
  return {
    id: i.id,
    width: i.width,
    height: i.height,
    mime: "image/png",
    size_bytes: 1200,
    original_name: i.name,
    created_at: NOW,
    used: Boolean(i.used),
    url: `/api/v1/studio/images/${i.id}/file`,
  };
}

export interface FakeDraft {
  id: string;
  kind: "cover_note" | "answer";
  question: string;
  body: string;
  origin: "model" | "edited";
  reads: number;
  failed?: boolean;
}

const COVER_BODY =
  "I built 30 REST endpoints with FastAPI and PostgreSQL for a placement portal, and I led a team of 4.";
const ANSWER_BODY =
  "I built 30 REST endpoints with FastAPI. I also run Kubernetes clusters for 400 users.";

function claimsOf(body: string) {
  const list: {
    text: string;
    kind: string;
    supported: boolean;
    source: string | null;
  }[] = [
    { text: "30", kind: "number", supported: true, source: "evidence" },
    { text: "fastapi", kind: "name", supported: true, source: "evidence" },
  ];
  if (/kubernetes/i.test(body))
    list.push({
      text: "kubernetes",
      kind: "name",
      supported: false,
      source: null,
    });
  if (/\b400\b/.test(body))
    list.push({ text: "400", kind: "number", supported: false, source: null });
  return list;
}

export function draftBody(d: FakeDraft) {
  const working = d.reads < 2;
  const claims = working ? [] : claimsOf(d.body);
  return {
    id: d.id,
    kind: d.kind,
    question: d.question,
    body: working ? "" : d.body,
    ui_state: d.failed ? "failed" : working ? "working" : "ready",
    origin: d.origin,
    error_message: d.failed
      ? "The writing service did not answer. Try again in a few minutes."
      : null,
    claims,
    unsupported_count: claims.filter((c) => !c.supported).length,
    word_count: d.body.split(/\s+/).filter(Boolean).length,
    evidence: working
      ? []
      : [
          {
            text: "Built 30 REST endpoints with FastAPI and PostgreSQL for a student placement portal.",
            source: "profile",
            cited: true,
          },
        ],
    updated_at: NOW,
  };
}

export const QUESTIONS = [
  { key: "why_role", text: "Why are you interested in this role?" },
  { key: "why_company", text: "Why do you want to work here?" },
  { key: "strength", text: "What is your strongest skill for this role?" },
];

export interface FakeImport {
  id: string;
  kind: "csv" | "xlsx" | "url";
  label: string;
  source: string;
  fail?: string;
  rows?: any[];
}

export function importBody(fake: Fake, batch: FakeImport) {
  const reads = fake.importReads[batch.id] ?? 0;
  const done = reads >= 2;
  const items =
    done && !batch.fail
      ? (batch.rows ?? [
          {
            row_number: 2,
            status: "created",
            code: null,
            message: null,
            title: "Backend engineer",
            source_url: null,
            posting_id: "job-1",
          },
          {
            row_number: 3,
            status: "rejected",
            code: "bad_link",
            message:
              "The link is not a web address that starts with http:// or https://.",
            title: "Broken link",
            source_url: null,
            posting_id: null,
          },
        ])
      : [];
  return {
    id: batch.id,
    kind: batch.kind,
    label: batch.label,
    default_source: batch.source,
    status: !done
      ? reads === 0
        ? "queued"
        : "running"
      : batch.fail
        ? "failed"
        : "done",
    error_message: done && batch.fail ? batch.fail : null,
    total_rows: items.length,
    created_count: items.filter((i: any) => i.status === "created").length,
    duplicate_count: items.filter((i: any) => i.status === "duplicate").length,
    rejected_count: items.filter((i: any) => i.status === "rejected").length,
    ignored_columns:
      done && !batch.fail && batch.kind !== "url" ? ["Salary"] : [],
    created_at: NOW,
    finished_at: done ? NOW : null,
    items,
  };
}

export async function fakeApi(
  page: Page,
  initial: Partial<Fake> = {},
): Promise<Fake> {
  const fake: Fake = {
    resume: null,
    entries: [],
    reads: 0,
    nextId: 10,
    meaning: "off",
    jobs: [],
    jobReads: {},
    analyses: {},
    studio: newStudio(),
    matches: [],
    imports: [],
    importReads: {},
    views: [],
    asked: [],
    images: [],
    themes: [],
    prep: newPrep(),
    plan: newPlan(),
    github: {
      available: false,
      connected: false,
      reads: 0,
      sync_state: "idle",
      sync_error: null,
      repos: [],
      revoked: true,
      calls: [],
    },
    drafts: {},
    checked: true,
    runs: [],
    verified: true,
    shortlist: {
      enabled: false,
      frequency: "weekly",
      weekday: 0,
      hour: 8,
      timezone: "UTC",
      max_items: 5,
      next_run_at: null,
      last_run_at: null,
    },
    prefs: {
      target_roles: [],
      authorized_countries: [],
      needs_sponsorship: null,
      locations: [],
      open_to_relocate: null,
      remote_preference: null,
      employment_types: [],
      min_salary_amount: null,
      min_salary_currency: null,
      exclusions: [],
    },
    ...initial,
  };
  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, json: body });
    // Only a preparation request has a JSON body to read. An upload body is raw bytes.
    const prepared = path.includes("/preparation")
      ? handlePreparation(
          path,
          method,
          {
            ...(request.postDataJSON() ?? {}),
            __replace: url.searchParams.get("replace") === "true",
          },
          fake,
        )
      : null;
    if (prepared)
      return route.fulfill({
        status: prepared.status,
        ...(prepared.json !== undefined ? { json: prepared.json } : {}),
      });
    if (path === "/api/v1/plan" && method === "GET")
      return json(planBody(fake.plan));
    if (path === "/api/v1/plan/upgrade" && method === "POST")
      return json(
        {
          code: "PAYMENTS_NOT_AVAILABLE",
          message:
            "Paid plans are not available yet. Nothing is charged and nothing is collected. The limits on your plan are shown below.",
        },
        409,
      );
    if (path === "/api/v1/status")
      return json({
        service: "api",
        version: "0",
        environment: "test",
        ready: true,
        checks: { database: "ok", migrations: "ok" },
      });
    if (path === "/api/v1/auth/session")
      return json({
        authenticated: true,
        user: USER,
        csrf_token: "t",
        config: { signup_mode: "invite", email_verification_required: false },
      });
    if (path === "/api/v1/profile/schema") return json(SPECS);
    if (path === "/api/v1/evidence/status") {
      const indexed = fake.entries.length;
      const embedded = fake.meaning === "ready" ? indexed : 0;
      return json({
        indexed,
        embedded,
        pending: indexed - embedded,
        meaning_search_configured: fake.meaning === "ready",
      });
    }
    if (path === "/api/v1/evidence/search") {
      const { query } = request.postDataJSON() as { query: string };
      const words = query.toLowerCase().split(/\s+/).filter(Boolean);
      const hits = fake.entries
        .map((entry) => ({
          entry,
          text: Object.values(entry.data).flat().join(". "),
        }))
        .filter(({ text }) =>
          words.every((word) => text.toLowerCase().includes(word)),
        )
        .map(({ entry, text }, index) => ({
          chunk_id: `c-${entry.id}`,
          entry_id: entry.id,
          source_type: "profile_entry",
          entry_type: entry.entry_type,
          text,
          score: 0.03 - index * 0.001,
          matched_by:
            fake.meaning === "ready" ? ["keyword", "meaning"] : ["keyword"],
          keyword_rank: index + 1,
          meaning_rank: fake.meaning === "ready" ? index + 1 : null,
          similarity: fake.meaning === "ready" ? 0.82 : null,
        }));
      return json({
        query,
        meaning_search_used: fake.meaning === "ready",
        note:
          fake.meaning === "ready"
            ? null
            : "Meaning search needs an AI key. Showing keyword matches only.",
        hits,
      });
    }
    if (path === "/api/v1/resume") {
      if (method === "POST") {
        fake.resume = resumeBody("uploaded");
        fake.reads = 0;
        return json(fake.resume, 201);
      }
      if (method === "DELETE") {
        fake.resume = null;
        return route.fulfill({ status: 204 });
      }
      // After an upload the fake "reads" the resume: uploaded, then parsing, then ready.
      if (fake.resume && fake.resume.ui_state === "uploaded") {
        fake.reads += 1;
        if (fake.reads === 2) fake.resume = resumeBody("parsing");
        if (fake.reads >= 3) {
          fake.resume = resumeBody("needs_correction");
          fake.entries = PARSED_ENTRIES();
        }
      } else if (fake.resume && fake.resume.ui_state === "parsing") {
        fake.resume = resumeBody("needs_correction");
        fake.entries = PARSED_ENTRIES();
      }
      return json(fake.resume);
    }
    if (path === "/api/v1/resume/confirm") {
      fake.resume = resumeBody("confirmed");
      return json(fake.resume);
    }
    if (path === "/api/v1/resume/reparse") {
      fake.resume = resumeBody("uploaded");
      fake.reads = 0;
      return json(fake.resume);
    }
    if (path === "/api/v1/profile/entries" && method === "GET")
      return json(fake.entries);
    if (path === "/api/v1/profile/entries" && method === "POST") {
      const body = request.postDataJSON() as {
        entry_type: string;
        data: Record<string, unknown>;
      };
      const spec = SPECS.find((s) => s.entry_type === body.entry_type);
      const errors: Record<string, string> = {};
      for (const f of spec?.fields ?? [])
        if (f.required && !body.data[f.name])
          errors[f.name] = "This is required.";
      if (Object.keys(errors).length)
        return json(
          {
            code: "VALIDATION_FAILED",
            message: "Some details need fixing.",
            fields: errors,
          },
          422,
        );
      const entry = makeEntry(
        `e${fake.nextId++}`,
        body.entry_type,
        body.data,
        "user",
      );
      fake.entries.push(entry);
      return json(entry, 201);
    }
    const match = path.match(/^\/api\/v1\/profile\/entries\/(.+)$/);
    if (match) {
      const entry = fake.entries.find((e) => e.id === match[1]);
      if (!entry)
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      if (method === "PATCH") {
        entry.data = (
          request.postDataJSON() as { data: Record<string, unknown> }
        ).data;
        entry.user_edited = true;
        entry.flags = flagsFor(entry.entry_type, entry.data);
        return json(entry);
      }
      if (method === "DELETE") {
        fake.entries = fake.entries.filter((e) => e.id !== entry.id);
        return route.fulfill({ status: 204 });
      }
    }
    if (path === "/api/v1/profile/preferences") {
      if (method === "PUT") {
        fake.prefs = request.postDataJSON() as Record<string, unknown>;
      }
      return json(fake.prefs);
    }
    if (path === "/api/v1/jobs" && method === "GET") {
      return json(
        fake.jobs.map((job) => {
          const { text, facts, requirements, eligibility_detail, ...summary } =
            jobBody(job);
          void text;
          void facts;
          void requirements;
          void eligibility_detail;
          return summary;
        }),
      );
    }
    if (path === "/api/v1/jobs" && method === "POST") {
      const body = request.postDataJSON() as {
        source_name: string;
        source_url: string | null;
        text: string;
      };
      if (body.text.trim().length < 100)
        return json(
          {
            code: "VALIDATION_FAILED",
            message: "Some details need fixing.",
            fields: {
              text: "This looks too short to be a job posting. Paste the whole description.",
            },
          },
          422,
        );
      const existing = fake.jobs.find(
        (j) => j.text.trim().toLowerCase() === body.text.trim().toLowerCase(),
      );
      if (existing)
        return json({ job: jobBody(existing), duplicate: true }, 200);
      const job: FakeJob = {
        id: `job-${fake.nextId++}`,
        text: body.text,
        source: body.source_name,
        url: body.source_url,
        state: "reading",
      };
      fake.jobs.unshift(job);
      fake.jobReads[job.id] = 0;
      return json({ job: jobBody(job), duplicate: false }, 201);
    }
    if (path === "/api/v1/studio/images" && method === "GET") {
      return json({
        images: fake.images.map(imageBody),
        count: fake.images.length,
        max_images: 20,
        max_bytes: 12582912,
        used_bytes: fake.images.length * 1200,
        accepted: ["JPEG", "PNG", "WebP"],
      });
    }
    if (path === "/api/v1/studio/images" && method === "POST") {
      const name = decodeURIComponent(
        request.headers()["x-filename"] ?? "picture.png",
      );
      if (/\.svg$/i.test(name))
        return json(
          {
            code: "IMAGE_REJECTED",
            message:
              "This kind of picture is not accepted. Choose a JPEG, PNG or WebP image. SVG, GIF, HEIC and other types are not used, because they can carry more than a picture.",
          },
          422,
        );
      if (/huge/i.test(name))
        return json(
          {
            code: "IMAGE_REJECTED",
            message:
              "This picture is much larger than a resume needs. Choose one under 24 megapixels, or resize it first.",
          },
          422,
        );
      const image: FakeImage = {
        id: `img-${fake.nextId++}`,
        name,
        width: 800,
        height: 1000,
      };
      fake.images.unshift(image);
      return json(imageBody(image), 201);
    }
    const imageFile = path.match(/^\/api\/v1\/studio\/images\/([^/]+)\/file$/);
    if (imageFile && method === "GET")
      return route.fulfill({
        status: 200,
        contentType: "image/png",
        body: TINY_PNG,
      });
    const imageOne = path.match(/^\/api\/v1\/studio\/images\/([^/]+)$/);
    if (imageOne && method === "DELETE") {
      const image = fake.images.find((i) => i.id === imageOne[1]);
      if (!image)
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      if (image.used)
        return json(
          {
            code: "IMAGE_LIMIT",
            message:
              "This picture is used in one of your resumes, or in a saved version of one. Remove it from there first, or delete that resume.",
          },
          409,
        );
      fake.images = fake.images.filter((i) => i.id !== image.id);
      return route.fulfill({ status: 204 });
    }
    if (path === "/api/v1/github" && method === "GET") {
      const g = fake.github;
      if (
        g.connected &&
        (g.sync_state === "queued" || g.sync_state === "syncing")
      ) {
        g.reads += 1;
        if (g.reads >= 2) {
          g.sync_state = "idle";
          if (g.repos.length === 0) g.repos = githubRepos();
          // The worker makes entries for the chosen repositories.
          fake.entries = fake.entries.filter(
            (e) => e.source !== "github" || e.user_edited,
          );
          for (const r of g.repos.filter((x) => x.selected)) {
            if (
              !fake.entries.some(
                (e) => e.source === "github" && e.data.name === r.name,
              )
            )
              fake.entries.push({
                ...makeEntry(
                  `gh${r.id}`,
                  "project",
                  { name: r.name, description: r.description, url: r.url },
                  "user",
                ),
                source: "github",
              });
          }
        }
      }
      return json({
        available: g.available,
        connected: g.connected,
        login: g.connected ? "asha" : null,
        profile_url: g.connected ? "https://github.com/asha" : null,
        scope: "",
        scope_sentence:
          "Provenance asks GitHub for no permissions at all. That gives it read access to public information only: your public repositories and their README files. It cannot see private repositories, cannot change anything on GitHub, and never sees your password.",
        sync_state: g.sync_state,
        sync_error: g.sync_error,
        connected_at: g.connected ? NOW : null,
        last_synced_at: g.connected && g.sync_state === "idle" ? NOW : null,
        repos: g.repos,
        max_selected: 12,
        entries_from_github: fake.entries.filter((e) => e.source === "github")
          .length,
        platforms: [
          {
            name: "LinkedIn",
            why: "LinkedIn does not allow other products to read your profile.",
            what: "Download your profile as a PDF from LinkedIn and upload it under Your resume.",
          },
          {
            name: "Anywhere else",
            why: "A portfolio, a paper or a talk is evidence too.",
            what: "Add it as an entry by hand with its link.",
          },
        ],
      });
    }
    if (path === "/api/v1/github/start" && method === "POST") {
      fake.github.calls.push("start");
      if (!fake.github.available)
        return json(
          {
            code: "GITHUB_NOT_CONFIGURED",
            message:
              "GitHub is not set up on this server yet, so it cannot be connected. Nothing was changed.",
          },
          503,
        );
      return json({
        authorize_url:
          "https://github.com/login/oauth/authorize?client_id=cid&state=" +
          "s".repeat(40),
      });
    }
    if (path === "/api/v1/github/callback" && method === "POST") {
      const body = request.postDataJSON() as { code: string; state: string };
      fake.github.calls.push(`callback:${body.code}`);
      if (body.code === "bad")
        return json(
          {
            code: "GITHUB_INVALID_CODE",
            message:
              "GitHub did not accept that sign-in. Start again from the Connect GitHub button.",
          },
          400,
        );
      fake.github.connected = true;
      fake.github.sync_state = "queued";
      fake.github.reads = 0;
      return json({ login: "asha" });
    }
    if (path === "/api/v1/github/sync" && method === "POST") {
      fake.github.calls.push("sync");
      fake.github.sync_state = "queued";
      fake.github.reads = 0;
      return route.fulfill({ status: 202 });
    }
    if (path === "/api/v1/github/repos" && method === "PUT") {
      const body = request.postDataJSON() as { repo_ids: number[] };
      fake.github.calls.push(`repos:${body.repo_ids.join(",")}`);
      if (body.repo_ids.length > 12)
        return json(
          {
            code: "GITHUB_TOO_MANY_SELECTED",
            message:
              "Choose at most 12 repositories. Fewer, better chosen ones read better.",
          },
          400,
        );
      for (const r of fake.github.repos)
        r.selected = body.repo_ids.includes(r.id);
      fake.github.sync_state = "queued";
      fake.github.reads = 0;
      return route.fulfill({ status: 202 });
    }
    if (path === "/api/v1/github/disconnect" && method === "POST") {
      const body = request.postDataJSON() as { keep_entries: boolean };
      fake.github.calls.push(`disconnect:${body.keep_entries}`);
      const removed = fake.entries.filter(
        (e) => e.source === "github" && !e.user_edited,
      ).length;
      fake.entries = body.keep_entries
        ? fake.entries.map((e) =>
            e.source === "github" ? { ...e, source: "user" as const } : e,
          )
        : fake.entries.filter((e) => e.source !== "github" || e.user_edited);
      fake.github.connected = false;
      fake.github.repos = [];
      fake.github.sync_state = "idle";
      return json({
        revoked: fake.github.revoked,
        entries_removed: body.keep_entries ? 0 : removed,
      });
    }
    if (path === "/api/v1/studio/themes" && method === "GET") {
      const sorted = [...fake.themes].sort((a, b) =>
        a.name.toLowerCase().localeCompare(b.name.toLowerCase()),
      );
      return json({ themes: sorted, count: sorted.length, max_themes: 20 });
    }
    if (path === "/api/v1/studio/themes" && method === "POST") {
      const body = request.postDataJSON() as Omit<
        FakeTheme,
        "id" | "updated_at"
      >;
      if (!body.name?.trim())
        return json(
          {
            code: "VALIDATION_FAILED",
            message: "The theme needs a change before it can be saved.",
            fields: { name: "Give the theme a name." },
          },
          422,
        );
      if (
        fake.themes.some(
          (t) => t.name.toLowerCase() === body.name.trim().toLowerCase(),
        )
      )
        return json(
          {
            code: "THEME_NAME_TAKEN",
            message:
              "You already have a theme with that name. Choose another name.",
            fields: {
              name: "You already have a theme with that name. Choose another name.",
            },
          },
          409,
        );
      const theme: FakeTheme = {
        ...body,
        name: body.name.trim(),
        id: `theme-${fake.nextId++}`,
        updated_at: NOW,
      };
      fake.themes.push(theme);
      return json(theme, 201);
    }
    const themeOne = path.match(/^\/api\/v1\/studio\/themes\/([^/]+)$/);
    if (themeOne && method === "PUT") {
      const theme = fake.themes.find((t) => t.id === themeOne[1]);
      if (!theme)
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      const body = request.postDataJSON() as Omit<
        FakeTheme,
        "id" | "updated_at"
      >;
      if (
        fake.themes.some(
          (t) =>
            t.id !== theme.id &&
            t.name.toLowerCase() === body.name.trim().toLowerCase(),
        )
      )
        return json(
          {
            code: "THEME_NAME_TAKEN",
            message:
              "You already have a theme with that name. Choose another name.",
            fields: {
              name: "You already have a theme with that name. Choose another name.",
            },
          },
          409,
        );
      Object.assign(theme, body, { name: body.name.trim(), updated_at: NOW });
      return json(theme);
    }
    if (themeOne && method === "DELETE") {
      if (!fake.themes.some((t) => t.id === themeOne[1]))
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      fake.themes = fake.themes.filter((t) => t.id !== themeOne[1]);
      return route.fulfill({ status: 204 });
    }
    const draftsMatch = path.match(
      /^\/api\/v1\/jobs\/([^/]+)\/drafts(?:\/([^/]+))?$/,
    );
    if (draftsMatch) {
      const jobId = draftsMatch[1] as string;
      const list = (fake.drafts[jobId] ??= []);
      if (!fake.jobs.find((j) => j.id === jobId))
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      const view = () => ({
        drafts: list.map((d) => {
          if (d.reads < 2) d.reads += 0;
          return draftBody(d);
        }),
        can_write: fake.checked,
        blocker: fake.checked
          ? null
          : "Check this job against your evidence first. A draft can only use what the check found.",
        questions: QUESTIONS,
        max_drafts: 8,
        label:
          "Draft. Written by AI from your own evidence. Check every line. Nothing is sent anywhere.",
      });
      if (!draftsMatch[2] && method === "GET") {
        list.forEach((d) => {
          if (d.reads < 2) d.reads += 1;
        });
        return json(view());
      }
      if (!draftsMatch[2] && method === "POST") {
        const body = request.postDataJSON() as {
          kind: "cover_note" | "answer";
          question: string;
          replace?: boolean;
        };
        if (!fake.checked)
          return json(
            {
              code: "ANALYSIS_NEEDED",
              message:
                "Check this job against your evidence first. A draft can only use what the check found.",
            },
            409,
          );
        if (body.kind === "answer" && body.question.trim().length < 8)
          return json(
            {
              code: "VALIDATION_FAILED",
              message: "Some details need fixing.",
              fields: {
                question:
                  "Write the question you want to answer, or choose one from the list.",
              },
            },
            422,
          );
        const existing = list.find(
          (d) =>
            d.kind === body.kind &&
            d.question.toLowerCase() === body.question.trim().toLowerCase(),
        );
        if (existing && existing.origin === "edited" && !body.replace)
          return json(
            {
              code: "EDITED_DRAFT",
              message:
                "You edited this draft. Writing it again replaces your edits. Confirm to go ahead.",
            },
            409,
          );
        const text = body.kind === "cover_note" ? COVER_BODY : ANSWER_BODY;
        if (existing) {
          existing.body = text;
          existing.origin = "model";
          existing.reads = 0;
          existing.failed = false;
        } else
          list.push({
            id: `draft-${fake.nextId++}`,
            kind: body.kind,
            question: body.kind === "answer" ? body.question.trim() : "",
            body: text,
            origin: "model",
            reads: 0,
            failed: body.question.includes("FAIL"),
          });
        return json(view(), 202);
      }
      const draft = list.find((d) => d.id === draftsMatch[2]);
      if (!draft)
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      if (method === "PUT") {
        draft.body = (request.postDataJSON() as { body: string }).body.trim();
        draft.origin = "edited";
        draft.failed = false;
        return json(draftBody(draft));
      }
      if (method === "DELETE") {
        fake.drafts[jobId] = list.filter((d) => d.id !== draft.id);
        return route.fulfill({ status: 204 });
      }
    }
    const shortlistBody = () => ({
      settings: {
        ...fake.shortlist,
        schedule_text:
          fake.shortlist.frequency === "daily"
            ? `Every day at ${String(fake.shortlist.hour).padStart(2, "0")}:00 (${fake.shortlist.timezone})`
            : `Every Monday at ${String(fake.shortlist.hour).padStart(2, "0")}:00 (${fake.shortlist.timezone})`,
      },
      runs: fake.runs,
      email_verified: fake.verified,
      blocker: fake.verified
        ? null
        : "Verify your email address first. The shortlist is only sent to a verified address.",
      delivery_note:
        "Development mode: email is not sent. It is written to the worker log (docker compose logs worker).",
    });
    if (path === "/api/v1/shortlist" && method === "GET")
      return json(shortlistBody());
    if (path === "/api/v1/shortlist" && method === "PUT") {
      const body = request.postDataJSON() as typeof fake.shortlist;
      if (body.enabled && !fake.verified)
        return json(
          {
            code: "EMAIL_NOT_VERIFIED",
            message:
              "Verify your email address first. The shortlist is only sent to a verified address.",
          },
          409,
        );
      if (body.timezone === "Mars/Base")
        return json(
          {
            code: "VALIDATION_FAILED",
            message: "Some details need fixing.",
            fields: { timezone: "Choose a time zone from the list." },
          },
          422,
        );
      fake.shortlist = {
        ...body,
        next_run_at: body.enabled ? "2026-11-09T02:30:00Z" : null,
        last_run_at: fake.shortlist.last_run_at,
      };
      return json(shortlistBody());
    }
    if (path === "/api/v1/shortlist/preview" && method === "GET") {
      const items = fake.jobs
        .filter(
          (j) =>
            j.state === "ready" &&
            (j.dstate ?? "new") === "new" &&
            (j.band === "strong" || j.band === "good"),
        )
        .map((j) => ({
          id: j.id,
          title: j.title ?? null,
          company: j.company ?? null,
          location: j.place ?? null,
          band: j.band ?? null,
          eligibility: j.elig ?? null,
          reason: `${j.band === "strong" ? "Strong" : "Good"} match: 9 of 11 required requirements supported (8 fully, 1 partly). Nothing stands in your way.`,
        }));
      return json({
        items,
        note: items.length
          ? "These are the jobs that would be in an email now."
          : "Nothing would be sent now. A job needs a finished evidence check, a Strong or Good fit, nothing in the way, and not to have been in an earlier email.",
      });
    }
    if (path === "/api/v1/shortlist/send" && method === "POST") {
      if (!fake.verified)
        return json(
          {
            code: "EMAIL_NOT_VERIFIED",
            message:
              "Verify your email address first. The shortlist is only sent to a verified address.",
          },
          409,
        );
      fake.runs.unshift({
        outcome: "sent",
        outcome_text: "Sent",
        item_count: 1,
        manual: true,
        at: NOW,
      });
      return json(
        {
          queued: true,
          message:
            "Queued. If anything is worth a look it will arrive shortly. If not, the list below says so.",
        },
        202,
      );
    }
    if (path === "/api/v1/workbench" && method === "GET") {
      const q = url.searchParams;
      fake.asked.push(url.search);
      const view =
        q.get("view") && VIEW_STATES[q.get("view") as string]
          ? (q.get("view") as string)
          : "active";
      const text = (q.get("q") ?? "")
        .toLowerCase()
        .split(/\s+/)
        .filter(Boolean);
      const all = fake.jobs.map(workRow);
      const inView = all.filter((r) =>
        (VIEW_STATES[view] ?? []).includes(r.decision.state),
      );
      const list = (k: string) => q.getAll(k);
      let rows = inView.filter((r) => {
        const hay =
          `${r.title ?? ""} ${r.company ?? ""} ${r.location ?? ""} ${r.source_name} ${fake.jobs.find((j) => j.id === r.id)?.note ?? ""}`.toLowerCase();
        if (!text.every((w) => hay.includes(w))) return false;
        if (
          list("work_mode").length &&
          !list("work_mode").includes(r.work_mode ?? "")
        )
          return false;
        if (
          list("eligibility").length &&
          !list("eligibility").includes(r.eligibility ?? "")
        )
          return false;
        if (list("band").length && !list("band").includes(r.band ?? ""))
          return false;
        if (list("source").length && !list("source").includes(r.source_name))
          return false;
        if (
          q.get("company") &&
          !(r.company ?? "")
            .toLowerCase()
            .includes((q.get("company") as string).toLowerCase())
        )
          return false;
        if (
          q.get("location") &&
          !(r.location ?? "")
            .toLowerCase()
            .includes((q.get("location") as string).toLowerCase())
        )
          return false;
        return true;
      });
      const sort = q.get("sort") ?? "added";
      const natural = sort === "added" || sort === "applied";
      const desc = q.get("desc") === null ? natural : q.get("desc") === "true";
      const key = (r: (typeof rows)[number]) =>
        sort === "title"
          ? (r.title ?? "").toLowerCase()
          : sort === "company"
            ? (r.company ?? "").toLowerCase()
            : r.created_at;
      rows = [...rows].sort(
        (a, b) =>
          (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0) * (desc ? -1 : 1),
      );
      const count = (get: (r: (typeof all)[number]) => string | null) =>
        inView.reduce<Record<string, number>>((m, r) => {
          const v = get(r);
          if (v) m[v] = (m[v] ?? 0) + 1;
          return m;
        }, {});
      const stored: Record<string, any> = { view, sort };
      return json({
        rows,
        total: rows.length,
        query: stored,
        truncated: false,
        facets: {
          views: Object.fromEntries(
            Object.entries(VIEW_STATES).map(([name, states]) => [
              name,
              all.filter((r) => states.includes(r.decision.state)).length,
            ]),
          ),
          work_modes: count((r) => r.work_mode),
          eligibility: count((r) => r.eligibility),
          bands: count((r) => r.band),
          employment_types: count((r) => r.employment_type),
          seniorities: count((r) => r.seniority),
          sources: count((r) => r.source_name),
        },
      });
    }
    if (path === "/api/v1/workbench/bulk" && method === "POST") {
      const body = request.postDataJSON() as { ids: string[]; action: string };
      const results = body.ids.map((id) => {
        const job = fake.jobs.find((j) => j.id === id);
        if (!job) return { id, ok: false, state: null, message: "Not found." };
        const refusal = moveJob(job, body.action);
        return {
          id,
          ok: refusal === null,
          state: job.dstate ?? "new",
          message: refusal,
        };
      });
      const done = results.filter((r) => r.ok).length;
      const reverse = REVERSE[body.action];
      return json({
        results,
        done,
        skipped: results.length - done,
        undo: reverse && done ? reverse : null,
        undo_label: reverse && done ? ACTION_LABEL[reverse] : null,
      });
    }
    if (path === "/api/v1/workbench/views" && method === "GET")
      return json(fake.views);
    if (path === "/api/v1/workbench/views" && method === "POST") {
      const body = request.postDataJSON() as {
        name: string;
        query: Record<string, any>;
      };
      if (
        fake.views.some(
          (v) => v.name.toLowerCase() === body.name.trim().toLowerCase(),
        )
      )
        return json(
          {
            code: "VIEW_NAME_TAKEN",
            message: "You already have a saved view with that name.",
            fields: { name: "You already have a saved view with that name." },
          },
          409,
        );
      const view = {
        id: `view-${fake.nextId++}`,
        name: body.name.trim(),
        query: body.query,
        created_at: NOW,
      };
      fake.views.push(view);
      return json(view, 201);
    }
    const viewMatch = path.match(/^\/api\/v1\/workbench\/views\/([^/]+)$/);
    if (viewMatch && method === "DELETE") {
      fake.views = fake.views.filter((v) => v.id !== viewMatch[1]);
      return route.fulfill({ status: 204 });
    }
    const decisionMatch = path.match(
      /^\/api\/v1\/jobs\/([^/]+)\/(decision|note)$/,
    );
    if (decisionMatch) {
      const job = fake.jobs.find((j) => j.id === decisionMatch[1]);
      if (!job) return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      if (decisionMatch[2] === "note") {
        job.note = (request.postDataJSON() as { note: string }).note.trim();
        return json(decisionBody(job));
      }
      const body = request.postDataJSON() as {
        action: string;
        applied_on?: string;
      };
      const refusal = moveJob(job, body.action);
      if (refusal)
        return json({ code: "DECISION_NOT_ALLOWED", message: refusal }, 409);
      if (body.action === "mark_applied" && body.applied_on)
        job.appliedAt = `${body.applied_on}T12:00:00Z`;
      const reverse = REVERSE[body.action];
      return json({
        decision: decisionBody(job),
        undo: reverse ?? null,
        undo_label: reverse ? ACTION_LABEL[reverse] : null,
      });
    }
    const addMatch = path.match(/^\/api\/v1\/search\/jobs\/([^/]+)\/add$/);
    if (addMatch && method === "POST") {
      const job: FakeJob = {
        id: `job-${fake.nextId++}`,
        text: "Backend Engineer at Palantir. Build data systems used by governments and companies.",
        source: "Company career page",
        url: "https://jobs.lever.co/palantir/1",
        state: "reading",
        acquisition: "source_job",
      };
      fake.jobs.unshift(job);
      fake.jobReads[job.id] = 0;
      return json({ job: jobBody(job), duplicate: false }, 201);
    }
    if (path === "/api/v1/jobs/manual" && method === "POST") {
      const body = request.postDataJSON() as {
        title: string;
        description: string;
        source_name: string;
        source_url: string | null;
      };
      if (body.title.length + body.description.length < 100)
        return json(
          {
            code: "VALIDATION_FAILED",
            message: "Some details need fixing.",
            fields: {
              description:
                "The description is under 100 characters. Paste the whole posting.",
            },
          },
          422,
        );
      const job: FakeJob = {
        id: `job-${fake.nextId++}`,
        text: `Title: ${body.title}

${body.description}`,
        source: body.source_name,
        url: body.source_url,
        state: "reading",
      };
      fake.jobs.unshift(job);
      fake.jobReads[job.id] = 0;
      return json({ job: jobBody(job), duplicate: false }, 201);
    }
    if (path === "/api/v1/imports" && method === "GET") {
      return json(
        fake.imports.map((b) => {
          const { items, ...summary } = importBody(fake, b);
          void items;
          return summary;
        }),
      );
    }
    if (path === "/api/v1/imports/url" && method === "POST") {
      const body = request.postDataJSON() as {
        url: string;
        source_name: string;
      };
      const refusal = !body.url.startsWith("https://")
        ? "Only secure (https) addresses are used."
        : /linkedin\.com/.test(body.url)
          ? "This site does not allow automated reading. Open the posting yourself, copy the description and paste it instead."
          : /localhost|127\.0\.0\.1/.test(body.url)
            ? "That address is not on the public internet."
            : null;
      if (refusal)
        return json(
          {
            code: "VALIDATION_FAILED",
            message: "Some details need fixing.",
            fields: { url: refusal },
          },
          422,
        );
      const batch: FakeImport = {
        id: `imp-${fake.nextId++}`,
        kind: "url",
        label: new URL(body.url).hostname,
        source: body.source_name,
        rows: [
          {
            row_number: 1,
            status: "created",
            code: null,
            message: null,
            title: "Backend engineer",
            source_url: body.url,
            posting_id: "job-1",
          },
        ],
      };
      fake.imports.unshift(batch);
      fake.importReads[batch.id] = 0;
      return json(importBody(fake, batch), 202);
    }
    if (path === "/api/v1/imports/file" && method === "POST") {
      const name = decodeURIComponent(
        request.headers()["x-filename"] ?? "jobs.csv",
      );
      const batch: FakeImport = {
        id: `imp-${fake.nextId++}`,
        kind: name.endsWith(".xlsx") ? "xlsx" : "csv",
        label: name,
        source: decodeURIComponent(
          request.headers()["x-source-name"] ?? "Other",
        ),
        ...(name.startsWith("bad")
          ? {
              fail: "No column holds the job description. Name one of the columns Description, Job description, Details, Posting or Text.",
            }
          : {}),
      };
      fake.imports.unshift(batch);
      fake.importReads[batch.id] = 0;
      return json(importBody(fake, batch), 202);
    }
    const importMatch = path.match(/^\/api\/v1\/imports\/([^/]+)$/);
    if (importMatch && method === "GET") {
      const batch = fake.imports.find((b) => b.id === importMatch[1]);
      if (!batch)
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      fake.importReads[batch.id] = (fake.importReads[batch.id] ?? 0) + 1;
      return json(importBody(fake, batch));
    }
    const fontMatch = path.match(/^\/api\/v1\/studio\/fonts\/([\w.-]+\.woff)$/);
    if (fontMatch) {
      return route.fulfill({
        path: resolve(
          process.cwd(),
          "../../packages/files/src/pv_files/assets/fonts",
          fontMatch[1] ?? "",
        ),
        contentType: "font/woff",
        headers: { "access-control-allow-origin": "*" },
      });
    }
    if (path === "/api/v1/studio/options") return json(STUDIO_OPTIONS);
    if (path === "/api/v1/search/sources") return json(SEARCH_SOURCES);
    if (path === "/api/v1/search/jobs") {
      const roles = new URL(request.url()).searchParams.getAll("roles");
      return json(
        FETCHED_JOBS.filter(
          (j) =>
            roles.length === 0 ||
            roles.some((r) => j.title.toLowerCase().includes(r.toLowerCase())),
        ),
      );
    }
    if (path === "/api/v1/search/plan" && method === "POST") {
      const body = request.postDataJSON() as {
        query?: string;
        intent?: Record<string, any>;
      };
      if (body.query === "no key")
        return json(
          {
            code: "AI_NOT_CONFIGURED",
            message:
              "Searching by sentence needs the AI service, which is not set up yet.",
          },
          503,
        );
      return json(searchPlan(body));
    }
    if (path === "/api/v1/studio/tailoring/jobs")
      return json(fake.studio.tailorJobs);
    const studioMatch = path.match(
      /^\/api\/v1\/studio\/(resumes|exports)(?:\/([^/]+))?(?:\/(.*))?$/,
    );
    if (studioMatch) {
      const [, kind, id, rest = ""] = studioMatch;
      const s = fake.studio;
      if (kind === "resumes" && !id) {
        if (method === "GET")
          return json(
            s.doc
              ? [
                  {
                    id: s.doc.id,
                    title: s.doc.title,
                    revision: s.doc.revision,
                    template: s.doc.template,
                    updated_at: NOW,
                  },
                ]
              : [],
          );
        if (method === "POST") {
          if (s.doc)
            return json(
              {
                code: "RESUME_LIMIT",
                message:
                  "The free plan keeps one resume. Delete it first to start another.",
              },
              409,
            );
          const body = request.postDataJSON() as {
            start: string;
            template: string;
          };
          s.doc =
            body.start === "profile"
              ? studioDoc("", body.template)
              : {
                  ...studioDoc("", body.template),
                  content: { ...studioContent(body.template), sections: [] },
                };
          s.versions = [];
          s.exportState = "none";
          return json(s.doc, 201);
        }
      }
      if (kind === "resumes" && id && s.doc && id === s.doc.id) {
        if (!rest && method === "GET") return json(s.doc);
        if (!rest && method === "DELETE") {
          s.doc = null;
          return route.fulfill({ status: 204 });
        }
        if (!rest && method === "PUT") {
          const body = request.postDataJSON() as {
            content: any;
            revision: number;
          };
          s.saves.push(body);
          if (s.conflict || body.revision !== s.doc.revision) {
            s.conflict = false;
            return json(
              {
                code: "REVISION_CONFLICT",
                message:
                  "This resume was changed somewhere else. Reload to see the latest version.",
              },
              409,
            );
          }
          if (body.content.style.accent === "#ffee88")
            return json(
              {
                code: "VALIDATION_FAILED",
                message: "Some details need fixing.",
                fields: {
                  "style.accent":
                    "This color is too light to read on white paper. Choose a darker one.",
                },
              },
              422,
            );
          s.doc = {
            ...s.doc,
            content: body.content,
            revision: s.doc.revision + 1,
            template: body.content.style.template,
          };
          return json({
            id: s.doc.id,
            title: s.doc.title,
            revision: s.doc.revision,
            template: s.doc.template,
            updated_at: NOW,
          });
        }
        if (rest === "tailoring" || rest.startsWith("tailoring/")) {
          const jobId = new URL(request.url()).searchParams.get("job_id");
          const view = () => ({
            ...s.tailoring,
            suggestions:
              s.tailoring!.ui_state === "ready" ? s.tailoring!.suggestions : [],
          });
          if (rest === "tailoring" && method === "POST") {
            const body = request.postDataJSON() as { job_id: string };
            s.tailorReads = 0;
            s.tailoring = {
              id: "t-1",
              job_id: body.job_id,
              job_title: "Data Analyst",
              company: "Kestrel",
              ui_state: "working",
              error_message: null,
              suggestions: s.tailorSuggestions.map((x) => structuredClone(x)),
              unclaimed: [
                {
                  text: "Experience with Tableau",
                  reason: "Nothing in your profile supports this yet.",
                },
              ],
            };
            return json(view(), 202);
          }
          if (rest === "tailoring" && method === "GET") {
            if (!s.tailoring || s.tailoring.job_id !== jobId) return json(null);
            if (s.tailoring.ui_state === "working") {
              s.tailorReads += 1;
              if (s.tailorReads >= 2) s.tailoring.ui_state = "ready";
            }
            return json(view());
          }
          const decision = rest.match(
            /^tailoring\/[^/]+\/suggestions\/([^/]+)(?:\/(accept|reject))?$/,
          );
          const item =
            decision &&
            s.tailoring?.suggestions.find((x: any) => x.id === decision[1]);
          if (!decision || !item)
            return json({ code: "NOT_FOUND", message: "Not found." }, 404);
          if (decision[2] === "reject") {
            item.status = "rejected";
            return json(item);
          }
          if (decision[2] === "accept") {
            if (item.blocked)
              return json(
                {
                  code: "UNSUPPORTED_CLAIMS",
                  message:
                    "This change adds something your evidence does not support. Edit it or reject it.",
                },
                409,
              );
            const body = request.postDataJSON() as { revision: number };
            if (body.revision !== s.doc.revision)
              return json(
                {
                  code: "REVISION_CONFLICT",
                  message:
                    "This resume was changed somewhere else. Reload to see the latest version.",
                },
                409,
              );
            const list =
              s.doc.content.sections[0].blocks[0].body.content[0].content;
            list.forEach((li: any, i: number) => {
              if (item.after_lines[i])
                li.content[0].content[0].text = item.after_lines[i];
            });
            s.doc = { ...s.doc, revision: s.doc.revision + 1 };
            item.status = "accepted";
            return json({
              suggestion: item,
              document: {
                id: s.doc.id,
                title: s.doc.title,
                revision: s.doc.revision,
                template: s.doc.template,
                updated_at: NOW,
              },
            });
          }
          if (method === "PUT") {
            const body = request.postDataJSON() as { after_lines: string[] };
            if (body.after_lines.length === 0)
              return json(
                {
                  code: "VALIDATION_FAILED",
                  message: "Some details need fixing.",
                  fields: {
                    after_lines:
                      "Write between 1 and 8 lines, each up to 300 characters.",
                  },
                },
                422,
              );
            const invented = /looker/i.test(body.after_lines.join(" "));
            item.after_lines = body.after_lines;
            item.edited = true;
            item.blocked = invented;
            item.claims = invented
              ? [
                  {
                    text: "looker",
                    kind: "name",
                    supported: false,
                    source: null,
                  },
                ]
              : [
                  {
                    text: "sql",
                    kind: "name",
                    supported: true,
                    source: "resume",
                  },
                ];
            return json(item);
          }
        }
        if (rest === "preview" && method === "POST")
          return json({
            html: previewHtml(
              (request.postDataJSON() as { content: any }).content,
            ),
          });
        if (rest === "versions" && method === "GET") return json(s.versions);
        if (
          rest.startsWith("versions/") &&
          rest.endsWith("/restore") &&
          method === "POST"
        ) {
          s.doc = {
            ...studioDoc("Restored Name", s.doc.template, s.doc.revision + 1),
          };
          return json(s.doc);
        }
        if (rest === "exports" && method === "GET") {
          if (s.exportState === "preparing") {
            s.exportReads += 1;
            if (s.exportReads >= 2) s.exportState = "ready";
          }
          if (s.exportState === "none") return json([]);
          return json([
            {
              id: "exp-1",
              revision: s.doc.revision,
              ui_state: s.exportState,
              size_bytes: s.exportState === "ready" ? 41000 : null,
              page_count: s.exportState === "ready" ? 2 : null,
              error_message:
                s.exportState === "failed"
                  ? "The PDF could not be made. Your resume is safe. Try again."
                  : null,
              created_at: NOW,
            },
          ]);
        }
        if (rest === "exports" && method === "POST") {
          s.exportState = "preparing";
          s.exportReads = 0;
          return json(
            {
              id: "exp-1",
              revision: s.doc.revision,
              ui_state: "preparing",
              size_bytes: null,
              page_count: null,
              error_message: null,
              created_at: NOW,
            },
            202,
          );
        }
      }
      if (kind === "exports" && rest === "download")
        return route.fulfill({
          status: 200,
          contentType: "application/pdf",
          body: "%PDF-1.7 fake",
        });
      return json({ code: "NOT_FOUND", message: "Not found." }, 404);
    }
    const analysisMatch = path.match(
      /^\/api\/v1\/jobs\/([^/]+)\/analysis(?:\/(.*))?$/,
    );
    if (analysisMatch) {
      const jobId = analysisMatch[1] ?? "";
      const rest = analysisMatch[2] ?? "";
      if (!fake.jobs.find((j) => j.id === jobId))
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      const a = fake.analyses[jobId];
      if (method === "POST" && rest === "") {
        fake.analyses[jobId] = {
          state: "working",
          reads: 0,
          ends: a?.ends ?? "ready",
          answered: a?.answered ?? false,
          feedback: {},
          blocker: null,
        };
        return json(analysisBody(fake.analyses[jobId]));
      }
      if (method === "POST" && rest.endsWith("/answer") && a) {
        a.answered = true;
        a.state = "working";
        a.reads = 0;
        a.ends = "ready";
        return json(analysisBody(a));
      }
      if (method === "POST" && rest.endsWith("/skip") && a) {
        a.state = "ready";
        return json(analysisBody(a));
      }
      if (method === "POST" && rest === "feedback" && a) {
        const body = request.postDataJSON() as {
          requirement_id: string | null;
          answer: "right" | "wrong";
        };
        a.feedback[body.requirement_id ?? "rec"] = body.answer;
        return json(analysisBody(a));
      }
      if (a && a.state === "working") {
        a.reads += 1;
        if (a.reads >= 3) a.state = a.ends;
      }
      return json(analysisBody(a));
    }
    const matchRoute = path.match(
      /^\/api\/v1\/jobs\/([^/]+)\/matches(?:\/([^/]+)\/(confirm|undo|reset))?$/,
    );
    if (matchRoute) {
      if (!fake.jobs.find((j) => j.id === matchRoute[1]))
        return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      if (matchRoute[3]) {
        const found = fake.matches.find((m) => m.group_id === matchRoute[2]);
        if (!found)
          return json({ code: "NOT_FOUND", message: "Not found." }, 404);
        found.state =
          matchRoute[3] === "confirm"
            ? "confirmed"
            : matchRoute[3] === "undo"
              ? "undone"
              : found.auto
                ? "auto"
                : "suggested";
      }
      return json(matchesBody(fake));
    }
    const jobMatch = path.match(/^\/api\/v1\/jobs\/([^/]+)(\/reanalyze)?$/);
    if (jobMatch) {
      const job = fake.jobs.find((j) => j.id === jobMatch[1]);
      if (!job) return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      if (method === "DELETE") {
        fake.jobs = fake.jobs.filter((j) => j.id !== job.id);
        return route.fulfill({ status: 204 });
      }
      if (jobMatch[2] && method === "POST") {
        job.state = "reading";
        fake.jobReads[job.id] = 0;
        return json(jobBody(job));
      }
      if (job.state === "reading") {
        fake.jobReads[job.id] = (fake.jobReads[job.id] ?? 0) + 1;
        if ((fake.jobReads[job.id] ?? 0) >= 3) job.state = "ready";
      }
      return json(jobBody(job));
    }
    return json({ code: "NOT_FOUND", message: "not mocked" }, 404);
  });
  return fake;
}

export function makeJob(
  state: FakeJob["state"],
  overrides: Partial<FakeJob> = {},
): FakeJob {
  return {
    id: "job-1",
    text: POSTING_TEXT,
    source: "Wellfound",
    url: null,
    state,
    ...overrides,
  };
}
