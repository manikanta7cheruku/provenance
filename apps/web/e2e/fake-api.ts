// A small stateful fake of the API for browser tests of the profile screen.
import { resolve } from "node:path";
import type { Page, Route } from "@playwright/test";

export const NOW = "2026-10-30T09:00:00Z";
export const USER = { id: "11111111-1111-4111-8111-111111111111", email: "asha@example.com", role: "USER", email_verified: true };

export const field = (name: string, label: string, kind: string, required = false, recommended = false, hint = "") => ({
  name, label, kind, max_length: 200, required, recommended, hint,
});
export const SPECS = [
  { entry_type: "education", label: "Education", plural: "Education", primary_field: "institution",
    fields: [field("institution", "Institution", "text", true), field("degree", "Degree", "text", false, true),
             field("end_date", "End or expected end", "date", false, true, "YYYY or YYYY-MM")] },
  { entry_type: "work", label: "Work experience", plural: "Work experience", primary_field: "company",
    fields: [field("company", "Company", "text", true), field("title", "Role", "text", true),
             field("start_date", "Start", "date", false, true, "YYYY or YYYY-MM"),
             field("highlights", "What you did", "list", false, true, "One achievement per line.")] },
  { entry_type: "skill", label: "Skill", plural: "Skills", primary_field: "name",
    fields: [field("name", "Skill", "text", true), field("category", "Group", "text")] },
];

export interface Entry { id: string; entry_type: string; data: Record<string, unknown>; user_edited: boolean;
  source: "resume" | "user"; flags: string[]; created_at: string; updated_at: string }

export function flagsFor(type: string, data: Record<string, unknown>): string[] {
  const spec = SPECS.find((s) => s.entry_type === type);
  return (spec?.fields ?? []).filter((f) => f.recommended && !data[f.name]).map((f) => f.name);
}

export function makeEntry(id: string, type: string, data: Record<string, unknown>, source: "resume" | "user" = "resume"): Entry {
  return { id, entry_type: type, data, user_edited: false, source, flags: flagsFor(type, data), created_at: NOW, updated_at: NOW };
}

export const PARSED_ENTRIES = (): Entry[] => [
  makeEntry("e1", "education", { institution: "BMS College of Engineering", degree: "B.E.", end_date: "2025" }),
  makeEntry("e2", "work", { company: "Kestrel Analytics", title: "Data Intern" }),
  makeEntry("e3", "skill", { name: "Python" }),
];

export function resumeBody(uiState: string, extra: Record<string, unknown> = {}) {
  return {
    id: "r1", original_filename: "Asha CV.pdf", file_kind: "pdf", size_bytes: 52000, ui_state: uiState,
    can_retry: uiState === "parsed" || uiState === "needs_correction" || uiState === "confirmed" || uiState === "failed",
    error_message: null, kept_entry_count: 3, dropped_entry_count: 1, flagged_entry_count: 2, page_count: 1,
    run_id: "run1", created_at: NOW, parsed_at: uiState === "uploaded" || uiState === "parsing" ? null : NOW,
    confirmed_at: uiState === "confirmed" ? NOW : null, ...extra,
  };
}


export interface FakeJob { id: string; text: string; source: string; url: string | null; state: "reading" | "ready" | "failed" }

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
    id: job.id, title: ready ? "Data Analyst, Early Careers" : null, company: ready ? "Fernlight Systems" : null,
    source_name: job.source, acquisition_method: "user_paste", ui_state: job.state, can_retry: job.state !== "reading",
    error_message: job.state === "failed" ? "The reading service did not answer. Your posting is saved. Try again in a few minutes." : null,
    eligibility: ready ? "requires_user_input" : null, work_mode: ready ? "hybrid" : null, location: ready ? "Bengaluru, India" : null,
    requirement_count: ready ? 2 : 0, created_at: NOW, source_url: job.url, visibility: "private",
    facts: ready ? {
      work_mode: { value: "hybrid", quote: "Bengaluru, India (Hybrid)" },
      location: { value: "Bengaluru, India", quote: "Bengaluru, India (Hybrid)" },
      min_years_experience: { value: 2, quote: "0-2 years of experience" },
      work_authorization_countries: { value: ["India"], quote: "Must be authorized to work in India." },
    } : {},
    requirements: ready ? [
      { id: "q1", ordinal: 0, text: "Write SQL to answer product questions", kind: "required", category: "skill", years_min: null, quote: "write SQL to answer questions from product teams", quote_start: 100, quote_end: 150 },
      { id: "q2", ordinal: 1, text: "Experience with Tableau", kind: "preferred", category: "skill", years_min: null, quote: "experience with Tableau", quote_start: 160, quote_end: 183 },
    ] : [],
    eligibility_detail: ready ? {
      state: "requires_user_input", rules_version: "eligibility-1",
      gates: [
        { gate: "authorization", label: "Work authorization and sponsorship", state: "requires_user_input", reason: "The posting requires permission to work in india. Add the countries where you can work without a visa in your preferences.", posting_quote: "Must be authorized to work in India." },
        { gate: "location", label: "Location and work mode", state: "uncertain", reason: "The role is hybrid in Bengaluru, India, a place you listed. You said you prefer remote work, so review it.", posting_quote: "Bengaluru, India (Hybrid)" },
        { gate: "seniority", label: "Experience asked for", state: "eligible", reason: "The posting asks for 2 years. Your profile shows about 1.", posting_quote: "0-2 years of experience" },
        { gate: "employment", label: "Kind of work", state: "eligible", reason: "You have not limited the kind of work.", posting_quote: null },
        { gate: "exclusions", label: "Things you chose to avoid", state: "eligible", reason: "You have not listed anything to avoid.", posting_quote: null },
      ],
    } : null,
    facts_dropped: ready ? 1 : 0, requirements_dropped: ready ? 1 : 0, prompt_version: "job-extract-1", run_id: "run-job", extracted_at: ready ? NOW : null,
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

const CITE_SQL = { chunk_id: "c1", quote: "Skill: SQL", source: "profile", entry_type: "skill", changed: false };
const CITE_STATS = { chunk_id: "c2", quote: "ran hypothesis tests on churn", source: "profile", entry_type: "internship", changed: false };
const CITE_ANSWER = { chunk_id: "c3", quote: "built three Power BI dashboards", source: "answer", entry_type: null, changed: false };

function verdictRow(id: string, requirement: string, kind: "required" | "preferred", verdict: string | null, extra: Record<string, unknown>, fb: FakeAnalysis) {
  return {
    requirement_id: id, requirement, kind, category: "skill", posting_quote: requirement, verdict,
    evidence_kind: null, confidence: verdict ? "none" : null, citations: [], reason: "", capped: false,
    feedback: fb.feedback[id] ?? null, ...extra,
  };
}

export function analysisBody(a: FakeAnalysis | undefined) {
  if (!a) {
    return {
      ui_state: "not_started", can_start: true, blocker: null, error_message: null, checked: 0, total: 4, score: null,
      verdicts: ["Write SQL to answer product questions", "Build dashboards in a BI tool", "Statistics including hypothesis testing"]
        .map((t, i) => verdictRow(`r${i}`, t, "required", null, {}, { feedback: {} } as FakeAnalysis))
        .concat([verdictRow("r3", "Experience with Tableau", "preferred", null, {}, { feedback: {} } as FakeAnalysis)]),
      gate_requirements: [{ requirement_id: "g1", requirement: "Authorized to work in India", kind: "required" }],
      questions: [], gaps: [], stale: false, recommendation_feedback: null, scoring_version: "scoring-1", prompt_version: null,
    };
  }
  const done = a.state === "ready";
  const asking = a.state === "needs_answer";
  const dash = a.answered
    ? verdictRow("r1", "Build dashboards in a BI tool", "required", "met", { evidence_kind: "direct", confidence: "high", citations: [CITE_ANSWER], reason: "You describe building dashboards." }, a)
    : verdictRow("r1", "Build dashboards in a BI tool", "required", asking || a.state === "working" ? null : "not_verified", { reason: "Nothing in your profile supports this yet." }, a);
  const verdicts = [
    verdictRow("r0", "Write SQL to answer product questions", "required", "met", { evidence_kind: "direct", confidence: "high", citations: [CITE_SQL], reason: "Your skills list names SQL." }, a),
    dash,
    verdictRow("r2", "Statistics including hypothesis testing", "required", "partial", { evidence_kind: "direct", confidence: "medium", citations: [CITE_STATS], reason: "One internship task used hypothesis tests." }, a),
    verdictRow("r3", "Experience with Tableau", "preferred", a.state === "working" ? null : "not_verified", { reason: "Nothing in your profile supports this yet." }, a),
  ];
  const met = a.answered ? 2 : 1;
  const failed = a.state === "failed";
  return {
    ui_state: a.state === "needs_answer" ? "needs_answer" : a.state, can_start: !["working", "needs_answer"].includes(a.state),
    blocker: a.blocker, error_message: failed ? "The checking service did not answer. Your results so far are saved. Check again in a few minutes and it continues where it stopped." : null,
    checked: verdicts.filter((v) => v.verdict).length, total: 4,
    score: done ? {
      scoring_version: "scoring-1", band: a.answered ? "good" : "review", required_total: 3, met, partial: 1, conflicting: 0, not_verified: a.answered ? 0 : 1,
      preferred_total: 1, preferred_supported: 0,
      reasons: [`${met + 1} of 3 required requirements supported (${met} fully, 1 partly).`, "Nice to have: 0 of 1 supported. These never lower the band.", "Eligibility: it needs an answer from you. See the checks above."],
    } : null,
    verdicts,
    gate_requirements: [{ requirement_id: "g1", requirement: "Authorized to work in India", kind: "required" }],
    questions: asking || a.answered ? [{ id: "q1", requirement_id: "r1", requirement: "Build dashboards in a BI tool", question: "Have you built dashboards in a course or project?", status: a.answered ? "answered" : "pending", answer: a.answered ? "I built three Power BI dashboards." : null }] : [],
    gaps: done && !a.answered ? [{ requirement_id: "r1", requirement: "Build dashboards in a BI tool", state: "not_verified", proof_needed: "An entry that shows you using it.", next_step: "Add a project or experience entry that says what you built with it." }] : [],
    stale: false, recommendation_feedback: a.feedback["rec"] ?? null, scoring_version: "scoring-1", prompt_version: "evidence-agent-1",
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
  tailorJobs: { job_id: string; title: string | null; company: string | null }[];
  /** The tailoring run once started: it reads as working twice, then ready. */
  tailoring: Record<string, any> | null;
  tailorReads: number;
  /** What the fake model suggests when asked. */
  tailorSuggestions: Record<string, any>[];
}

export function newStudio(): FakeStudio {
  return { doc: null, versions: [], exportReads: 0, exportState: "none", conflict: false, saves: [], tailorJobs: [], tailoring: null, tailorReads: 0, tailorSuggestions: [] };
}

export const STUDIO_OPTIONS = {
  templates: [
    { key: "classic", name: "Classic", description: "A serif name and headings over plain body text.", ats_safe: true },
    { key: "modern", name: "Modern", description: "Sans serif with an accent color.", ats_safe: true },
    { key: "compact", name: "Compact", description: "Tighter type and spacing.", ats_safe: true },
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
    { key: "source-merriweather", label: "Merriweather headings, Source Sans body" },
    { key: "playfair-source", label: "Playfair headings, Source Sans body" },
    { key: "lora", label: "Lora throughout" },
    { key: "merriweather", label: "Merriweather throughout" },
  ],
  sizes: ["small", "medium", "large"],
  spacings: ["tight", "normal", "relaxed"],
  margins: ["narrow", "normal", "wide"],
  dividers: ["none", "thin", "bold", "dotted"],
  papers: ["a4", "letter"],
  section_kinds: ["summary", "experience", "education", "projects", "skills", "certifications", "achievements", "custom"],
  max_resumes: 1,
};

export const SEARCH_SOURCES = [
  { key: "lever", display_name: "Lever postings", source_type: "ats_board", outcome: "unavailable", message: "Lever postings is currently unavailable. Reason: It is switched off. You can still import jobs you collected from Lever postings.", reason: "It is switched off.", import_available: true, compliance_status: "verified", terms_checked_at: "2026-11-02", terms_url: "https://www.lever.co/terms-of-service/", attribution_text: "" },
  { key: "linkedin", display_name: "LinkedIn", source_type: "user_import_only", outcome: "import_required", message: "Automated search for LinkedIn is not available. Import jobs by URL, paste, or CSV/XLSX and we will analyze them.", reason: "Automated access to this platform is not permitted, so jobs from it are imported by you.", import_available: true, compliance_status: "prohibited", terms_checked_at: "2026-11-02", terms_url: "https://www.linkedin.com/legal/user-agreement", attribution_text: "" },
];

export function searchPlan(body: { query?: string; intent?: Record<string, any> }) {
  const intent = body.intent ?? {};
  const companies: string[] = intent.companies ?? (body.query?.includes("Google") ? ["Google"] : body.query?.includes("Tata") ? ["Tata"] : []);
  return {
    interpreted_by: body.query !== undefined ? "the AI service" : "the fields you set",
    intent: { roles: intent.roles ?? ["Backend Engineer"], skills: [], min_years: null, max_years: null, locations: intent.locations ?? ["India"], work_mode: intent.work_mode ?? "any", employment_types: [], compensation: null, companies, sources: ["all_permitted"], exclusions: [] },
    headline: "No source can be searched automatically for this yet. You can import jobs and we will analyze them.",
    can_search_now: false,
    notes: [],
    sources: [
      { key: "linkedin", display_name: "LinkedIn", outcome: "import_required", message: SEARCH_SOURCES[1]!.message, reason: SEARCH_SOURCES[1]!.reason, import_available: true, named_by_person: false, notes: [] },
      { key: "lever", display_name: "Lever postings", outcome: "unavailable", message: SEARCH_SOURCES[0]!.message, reason: "It is switched off.", import_available: true, named_by_person: false, notes: [] },
    ],
    companies: companies.map((q) =>
      q === "Tata"
        ? { query: q, status: "ambiguous", route: "choose", message: "Which one did you mean by Tata? Tata Consultancy Services, Tata Motors.", company: null, source_key: null, candidates: [{ key: "tcs", name: "Tata Consultancy Services", score: 0.8 }, { key: "tata-motors", name: "Tata Motors", score: 0.8 }] }
        : { query: q, status: "resolved", route: "import", message: "No permitted source can be searched for " + q + ". Import jobs by URL, paste, or CSV/XLSX and we will analyze them.", company: { key: q.toLowerCase(), name: q, score: 1 }, source_key: null, candidates: [] },
    ),
    authorization: { countries: ["India"], needs_sponsorship: false, origin: "your profile" },
  };
}

export function studioContent(template = "classic", name = "") {
  return {
    version: 1,
    style: { template, font_pair: "plex-newsreader", size: "medium", spacing: "normal", margins: "normal", accent: "#222222", divider: "thin", paper: "a4" },
    header: { name, headline: "", contacts: [] },
    sections: [
      { id: "s1", kind: "experience", title: "Experience", blocks: [
        { id: "b1", heading: "Data Intern", subheading: "Kestrel Analytics", dates: "2025-06 to 2025-08", location: "",
          body: { type: "doc", content: [{ type: "bulletList", content: [{ type: "listItem", content: [{ type: "paragraph", content: [{ type: "text", text: "Cleaned six CSV sources with pandas" }] }] }] }] } },
      ] },
      { id: "s2", kind: "education", title: "Education", blocks: [
        { id: "b2", heading: "B.E. Computer Science", subheading: "BMS College of Engineering", dates: "2026", location: "", body: null },
      ] },
    ],
  };
}

export function studioDoc(name = "Asha Rao", template = "classic", revision = 1) {
  return { id: "doc-1", title: "My resume", revision, template, updated_at: NOW, content: studioContent(template, name) };
}


function para(text: string, marks: string[] = []) {
  return { type: "paragraph", content: [{ type: "text", text, ...(marks.length ? { marks: marks.map((type) => ({ type })) } : {}) }] };
}

function textEl(id: string, name: string, x: number, y: number, w: number, h: number, body: unknown, extra: Record<string, unknown> = {}) {
  return { id, kind: "text", name, x, y, w, h, locked: false, group: null, body, font: "body", size: 10.5, color: "ink", align: "left", line_height: 1.3, caps: false, ...extra };
}

/** A free canvas resume: a name, a headline, a rule, a role with a right-aligned date, and bullets. */
export function canvasContent(name = "Asha Rao") {
  const bullets = { type: "doc", content: [{ type: "bulletList", content: ["Cleaned six CSV sources with pandas", "Wrote SQL joins over 1.2 million rows"].map((line) => ({ type: "listItem", content: [para(line)] })) }] };
  return {
    version: 2,
    style: { template: "classic", font_pair: "plex-newsreader", accent: "#1f3d7a", ink: "#1b1b1b", muted: "#4a4a4a", tint: "#eef1f6", paper: "a4", margin_mm: 16 },
    pages: [{
      id: "pg1",
      elements: [
        textEl("name", "Name", 16, 16, 178, 11, { type: "doc", content: [para(name)] }, { font: "heading", size: 26, color: "accent", line_height: 1.1 }),
        textEl("headline", "Headline", 16, 29, 178, 6, { type: "doc", content: [para("Data analyst")] }, { size: 11 }),
        { id: "rule", kind: "shape", name: "Rule", x: 16, y: 38, w: 178, h: 0.4, locked: false, group: null, fill: "accent", stroke: "none", stroke_pt: 0, radius: 0 },
        textEl("role", "Role", 16, 44, 140, 6, { type: "doc", content: [para("Data Intern, Kestrel Analytics", ["bold"])] }),
        textEl("dates", "Dates", 158, 44, 36, 5, { type: "doc", content: [para("2025-06 to 2025-08")] }, { align: "right", size: 9.5, color: "muted" }),
        textEl("bullets", "Highlights", 16, 52, 178, 12, bullets),
      ],
    }],
  };
}

export function canvasDoc(name = "Asha Rao", revision = 1) {
  return { id: "doc-1", title: "My resume", revision, template: "classic", updated_at: NOW, content: canvasContent(name) };
}

export function previewHtml(content: any): string {
  const sections = (content.sections ?? []).map((s: any) => `<h2>${s.title}</h2>`).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Resume</title><style>body{margin:0;background:#e9e9e6;font-family:sans-serif}.sheet{width:794px;min-height:1123px;margin:0 auto;padding:60px;box-sizing:border-box;background:#fff}</style></head><body><main class="sheet"><h1>${content.header?.name ?? ""}</h1>${sections}</main></body></html>`;
}

export interface Fake { resume: ReturnType<typeof resumeBody> | null; entries: Entry[]; reads: number; prefs: Record<string, unknown>; nextId: number;
  /** Whether the fake backend has an AI key and embedded entries. */
  meaning: "off" | "ready";
  jobs: FakeJob[];
  jobReads: Record<string, number>;
  analyses: Record<string, FakeAnalysis>;
  studio: FakeStudio }

export async function fakeApi(page: Page, initial: Partial<Fake> = {}): Promise<Fake> {
  const fake: Fake = {
    resume: null, entries: [], reads: 0, nextId: 10, meaning: "off", jobs: [], jobReads: {}, analyses: {}, studio: newStudio(), prefs: {
      target_roles: [], authorized_countries: [], needs_sponsorship: null, locations: [], open_to_relocate: null,
      remote_preference: null, employment_types: [], min_salary_amount: null, min_salary_currency: null, exclusions: [],
    }, ...initial,
  };
  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });
    if (path === "/api/v1/status") return json({ service: "api", version: "0", environment: "test", ready: true, checks: { database: "ok", migrations: "ok" } });
    if (path === "/api/v1/auth/session") return json({ authenticated: true, user: USER, csrf_token: "t", config: { signup_mode: "invite", email_verification_required: false } });
    if (path === "/api/v1/profile/schema") return json(SPECS);
    if (path === "/api/v1/evidence/status") {
      const indexed = fake.entries.length;
      const embedded = fake.meaning === "ready" ? indexed : 0;
      return json({ indexed, embedded, pending: indexed - embedded, meaning_search_configured: fake.meaning === "ready" });
    }
    if (path === "/api/v1/evidence/search") {
      const { query } = request.postDataJSON() as { query: string };
      const words = query.toLowerCase().split(/\s+/).filter(Boolean);
      const hits = fake.entries
        .map((entry) => ({ entry, text: Object.values(entry.data).flat().join(". ") }))
        .filter(({ text }) => words.every((word) => text.toLowerCase().includes(word)))
        .map(({ entry, text }, index) => ({
          chunk_id: `c-${entry.id}`, entry_id: entry.id, source_type: "profile_entry", entry_type: entry.entry_type,
          text, score: 0.03 - index * 0.001, matched_by: fake.meaning === "ready" ? ["keyword", "meaning"] : ["keyword"],
          keyword_rank: index + 1, meaning_rank: fake.meaning === "ready" ? index + 1 : null,
          similarity: fake.meaning === "ready" ? 0.82 : null,
        }));
      return json({
        query, meaning_search_used: fake.meaning === "ready",
        note: fake.meaning === "ready" ? null : "Meaning search needs an AI key. Showing keyword matches only.",
        hits,
      });
    }
    if (path === "/api/v1/resume") {
      if (method === "POST") {
        fake.resume = resumeBody("uploaded");
        fake.reads = 0;
        return json(fake.resume, 201);
      }
      if (method === "DELETE") { fake.resume = null; return route.fulfill({ status: 204 }); }
      // After an upload the fake "reads" the resume: uploaded, then parsing, then ready.
      if (fake.resume && fake.resume.ui_state === "uploaded") {
        fake.reads += 1;
        if (fake.reads === 2) fake.resume = resumeBody("parsing");
        if (fake.reads >= 3) { fake.resume = resumeBody("needs_correction"); fake.entries = PARSED_ENTRIES(); }
      } else if (fake.resume && fake.resume.ui_state === "parsing") {
        fake.resume = resumeBody("needs_correction"); fake.entries = PARSED_ENTRIES();
      }
      return json(fake.resume);
    }
    if (path === "/api/v1/resume/confirm") { fake.resume = resumeBody("confirmed"); return json(fake.resume); }
    if (path === "/api/v1/resume/reparse") { fake.resume = resumeBody("uploaded"); fake.reads = 0; return json(fake.resume); }
    if (path === "/api/v1/profile/entries" && method === "GET") return json(fake.entries);
    if (path === "/api/v1/profile/entries" && method === "POST") {
      const body = request.postDataJSON() as { entry_type: string; data: Record<string, unknown> };
      const spec = SPECS.find((s) => s.entry_type === body.entry_type);
      const errors: Record<string, string> = {};
      for (const f of spec?.fields ?? []) if (f.required && !body.data[f.name]) errors[f.name] = "This is required.";
      if (Object.keys(errors).length) return json({ code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: errors }, 422);
      const entry = makeEntry(`e${fake.nextId++}`, body.entry_type, body.data, "user");
      fake.entries.push(entry);
      return json(entry, 201);
    }
    const match = path.match(/^\/api\/v1\/profile\/entries\/(.+)$/);
    if (match) {
      const entry = fake.entries.find((e) => e.id === match[1]);
      if (!entry) return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      if (method === "PATCH") {
        entry.data = (request.postDataJSON() as { data: Record<string, unknown> }).data;
        entry.user_edited = true;
        entry.flags = flagsFor(entry.entry_type, entry.data);
        return json(entry);
      }
      if (method === "DELETE") { fake.entries = fake.entries.filter((e) => e.id !== entry.id); return route.fulfill({ status: 204 }); }
    }
    if (path === "/api/v1/profile/preferences") {
      if (method === "PUT") { fake.prefs = request.postDataJSON() as Record<string, unknown>; }
      return json(fake.prefs);
    }
    if (path === "/api/v1/jobs" && method === "GET") {
      return json(fake.jobs.map((job) => {
        const { text, facts, requirements, eligibility_detail, ...summary } = jobBody(job);
        void text; void facts; void requirements; void eligibility_detail;
        return summary;
      }));
    }
    if (path === "/api/v1/jobs" && method === "POST") {
      const body = request.postDataJSON() as { source_name: string; source_url: string | null; text: string };
      if (body.text.trim().length < 100) return json({ code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: { text: "This looks too short to be a job posting. Paste the whole description." } }, 422);
      const existing = fake.jobs.find((j) => j.text.trim().toLowerCase() === body.text.trim().toLowerCase());
      if (existing) return json({ job: jobBody(existing), duplicate: true }, 200);
      const job: FakeJob = { id: `job-${fake.nextId++}`, text: body.text, source: body.source_name, url: body.source_url, state: "reading" };
      fake.jobs.unshift(job);
      fake.jobReads[job.id] = 0;
      return json({ job: jobBody(job), duplicate: false }, 201);
    }
    const fontMatch = path.match(/^\/api\/v1\/studio\/fonts\/([\w.-]+\.woff)$/);
    if (fontMatch) {
      return route.fulfill({
        path: resolve(process.cwd(), "../../packages/files/src/pv_files/assets/fonts", fontMatch[1] ?? ""),
        contentType: "font/woff",
        headers: { "access-control-allow-origin": "*" },
      });
    }
    if (path === "/api/v1/studio/options") return json(STUDIO_OPTIONS);
    if (path === "/api/v1/search/sources") return json(SEARCH_SOURCES);
    if (path === "/api/v1/search/plan" && method === "POST") {
      const body = request.postDataJSON() as { query?: string; intent?: Record<string, any> };
      if (body.query === "no key") return json({ code: "AI_NOT_CONFIGURED", message: "Searching by sentence needs the AI service, which is not set up yet." }, 503);
      return json(searchPlan(body));
    }
    if (path === "/api/v1/studio/tailoring/jobs") return json(fake.studio.tailorJobs);
    const studioMatch = path.match(/^\/api\/v1\/studio\/(resumes|exports)(?:\/([^/]+))?(?:\/(.*))?$/);
    if (studioMatch) {
      const [, kind, id, rest = ""] = studioMatch;
      const s = fake.studio;
      if (kind === "resumes" && !id) {
        if (method === "GET") return json(s.doc ? [{ id: s.doc.id, title: s.doc.title, revision: s.doc.revision, template: s.doc.template, updated_at: NOW }] : []);
        if (method === "POST") {
          if (s.doc) return json({ code: "RESUME_LIMIT", message: "The free plan keeps one resume. Delete it first to start another." }, 409);
          const body = request.postDataJSON() as { start: string; template: string };
          s.doc = body.start === "profile" ? studioDoc("", body.template) : { ...studioDoc("", body.template), content: { ...studioContent(body.template), sections: [] } };
          s.versions = [];
          s.exportState = "none";
          return json(s.doc, 201);
        }
      }
      if (kind === "resumes" && id && s.doc && id === s.doc.id) {
        if (!rest && method === "GET") return json(s.doc);
        if (!rest && method === "DELETE") { s.doc = null; return route.fulfill({ status: 204 }); }
        if (!rest && method === "PUT") {
          const body = request.postDataJSON() as { content: any; revision: number };
          s.saves.push(body);
          if (s.conflict || body.revision !== s.doc.revision) { s.conflict = false; return json({ code: "REVISION_CONFLICT", message: "This resume was changed somewhere else. Reload to see the latest version." }, 409); }
          if (body.content.style.accent === "#ffee88") return json({ code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: { "style.accent": "This color is too light to read on white paper. Choose a darker one." } }, 422);
          s.doc = { ...s.doc, content: body.content, revision: s.doc.revision + 1, template: body.content.style.template };
          return json({ id: s.doc.id, title: s.doc.title, revision: s.doc.revision, template: s.doc.template, updated_at: NOW });
        }
        if (rest === "tailoring" || rest.startsWith("tailoring/")) {
          const jobId = new URL(request.url()).searchParams.get("job_id");
          const view = () => ({ ...s.tailoring, suggestions: s.tailoring!.ui_state === "ready" ? s.tailoring!.suggestions : [] });
          if (rest === "tailoring" && method === "POST") {
            const body = request.postDataJSON() as { job_id: string };
            s.tailorReads = 0;
            s.tailoring = { id: "t-1", job_id: body.job_id, job_title: "Data Analyst", company: "Kestrel", ui_state: "working", error_message: null, suggestions: s.tailorSuggestions.map((x) => structuredClone(x)), unclaimed: [{ text: "Experience with Tableau", reason: "Nothing in your profile supports this yet." }] };
            return json(view(), 202);
          }
          if (rest === "tailoring" && method === "GET") {
            if (!s.tailoring || s.tailoring.job_id !== jobId) return json(null);
            if (s.tailoring.ui_state === "working") { s.tailorReads += 1; if (s.tailorReads >= 2) s.tailoring.ui_state = "ready"; }
            return json(view());
          }
          const decision = rest.match(/^tailoring\/[^/]+\/suggestions\/([^/]+)(?:\/(accept|reject))?$/);
          const item = decision && s.tailoring?.suggestions.find((x: any) => x.id === decision[1]);
          if (!decision || !item) return json({ code: "NOT_FOUND", message: "Not found." }, 404);
          if (decision[2] === "reject") { item.status = "rejected"; return json(item); }
          if (decision[2] === "accept") {
            if (item.blocked) return json({ code: "UNSUPPORTED_CLAIMS", message: "This change adds something your evidence does not support. Edit it or reject it." }, 409);
            const body = request.postDataJSON() as { revision: number };
            if (body.revision !== s.doc.revision) return json({ code: "REVISION_CONFLICT", message: "This resume was changed somewhere else. Reload to see the latest version." }, 409);
            const list = s.doc.content.sections[0].blocks[0].body.content[0].content;
            list.forEach((li: any, i: number) => { if (item.after_lines[i]) li.content[0].content[0].text = item.after_lines[i]; });
            s.doc = { ...s.doc, revision: s.doc.revision + 1 };
            item.status = "accepted";
            return json({ suggestion: item, document: { id: s.doc.id, title: s.doc.title, revision: s.doc.revision, template: s.doc.template, updated_at: NOW } });
          }
          if (method === "PUT") {
            const body = request.postDataJSON() as { after_lines: string[] };
            if (body.after_lines.length === 0) return json({ code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: { after_lines: "Write between 1 and 8 lines, each up to 300 characters." } }, 422);
            const invented = /looker/i.test(body.after_lines.join(" "));
            item.after_lines = body.after_lines;
            item.edited = true;
            item.blocked = invented;
            item.claims = invented ? [{ text: "looker", kind: "name", supported: false, source: null }] : [{ text: "sql", kind: "name", supported: true, source: "resume" }];
            return json(item);
          }
        }
        if (rest === "preview" && method === "POST") return json({ html: previewHtml((request.postDataJSON() as { content: any }).content) });
        if (rest === "versions" && method === "GET") return json(s.versions);
        if (rest.startsWith("versions/") && rest.endsWith("/restore") && method === "POST") {
          s.doc = { ...studioDoc("Restored Name", s.doc.template, s.doc.revision + 1) };
          return json(s.doc);
        }
        if (rest === "exports" && method === "GET") {
          if (s.exportState === "preparing") { s.exportReads += 1; if (s.exportReads >= 2) s.exportState = "ready"; }
          if (s.exportState === "none") return json([]);
          return json([{ id: "exp-1", revision: s.doc.revision, ui_state: s.exportState, size_bytes: s.exportState === "ready" ? 41000 : null, page_count: s.exportState === "ready" ? 2 : null, error_message: s.exportState === "failed" ? "The PDF could not be made. Your resume is safe. Try again." : null, created_at: NOW }]);
        }
        if (rest === "exports" && method === "POST") { s.exportState = "preparing"; s.exportReads = 0; return json({ id: "exp-1", revision: s.doc.revision, ui_state: "preparing", size_bytes: null, page_count: null, error_message: null, created_at: NOW }, 202); }
      }
      if (kind === "exports" && rest === "download") return route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.7 fake" });
      return json({ code: "NOT_FOUND", message: "Not found." }, 404);
    }
    const analysisMatch = path.match(/^\/api\/v1\/jobs\/([^/]+)\/analysis(?:\/(.*))?$/);
    if (analysisMatch) {
      const jobId = analysisMatch[1] ?? "";
      const rest = analysisMatch[2] ?? "";
      if (!fake.jobs.find((j) => j.id === jobId)) return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      const a = fake.analyses[jobId];
      if (method === "POST" && rest === "") {
        fake.analyses[jobId] = { state: "working", reads: 0, ends: a?.ends ?? "ready", answered: a?.answered ?? false, feedback: {}, blocker: null };
        return json(analysisBody(fake.analyses[jobId]));
      }
      if (method === "POST" && rest.endsWith("/answer") && a) { a.answered = true; a.state = "working"; a.reads = 0; a.ends = "ready"; return json(analysisBody(a)); }
      if (method === "POST" && rest.endsWith("/skip") && a) { a.state = "ready"; return json(analysisBody(a)); }
      if (method === "POST" && rest === "feedback" && a) {
        const body = request.postDataJSON() as { requirement_id: string | null; answer: "right" | "wrong" };
        a.feedback[body.requirement_id ?? "rec"] = body.answer;
        return json(analysisBody(a));
      }
      if (a && a.state === "working") {
        a.reads += 1;
        if (a.reads >= 3) a.state = a.ends;
      }
      return json(analysisBody(a));
    }
    const jobMatch = path.match(/^\/api\/v1\/jobs\/([^/]+)(\/reanalyze)?$/);
    if (jobMatch) {
      const job = fake.jobs.find((j) => j.id === jobMatch[1]);
      if (!job) return json({ code: "NOT_FOUND", message: "Not found." }, 404);
      if (method === "DELETE") { fake.jobs = fake.jobs.filter((j) => j.id !== job.id); return route.fulfill({ status: 204 }); }
      if (jobMatch[2] && method === "POST") { job.state = "reading"; fake.jobReads[job.id] = 0; return json(jobBody(job)); }
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


export function makeJob(state: FakeJob["state"], overrides: Partial<FakeJob> = {}): FakeJob {
  return { id: "job-1", text: POSTING_TEXT, source: "Wellfound", url: null, state, ...overrides };
}
