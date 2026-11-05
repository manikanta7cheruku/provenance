// A small stateful fake of the career preparation API, so the whole screen (what to prepare, practice
// material, messages, the mock interview, the plan and the company notes) is exercised in a real browser.

export interface FakeOutput { status: "queued" | "working" | "ready" | "failed"; reads: number; origin: "model" | "edited"; body: string; error: string | null; unsupported: string[] }

export interface FakeMockTurn { question: string; answer: string; rubric: { name: string; score: number; note: string }[]; total: number; maximum: number; unsupported_claims: string[]; follow_up: string; words: number }

export interface FakePrep {
  can_prepare: boolean;
  /** Make the written material contain a claim that is not in the evidence. */
  invented: boolean;
  /** Make a start fail the way an unconfigured writing service does. */
  failWith: string | null;
  outputs: Record<string, FakeOutput>;
  done: string[];
  date: string | null;
  company: { link: string; notes: string };
  mock: { id: string; state: "active" | "finished"; questions: string[]; turns: FakeMockTurn[] } | null;
  calls: string[];
}

export const newPrep = (over: Partial<FakePrep> = {}): FakePrep => ({
  can_prepare: true, invented: false, failWith: null, outputs: {}, done: [], date: null, company: { link: "", notes: "" }, mock: null, calls: [], ...over,
});

const CONCEPTS = [
  { requirement_id: "r-aws", text: "Experience with AWS", kind: "required", category: "skill", verdict: "not_verified", priority: "critical", priority_label: "Critical gap", difficulty: "hard", why: "The job requires it and your profile does not show it yet." },
  { requirement_id: "r-api", text: "Building REST APIs with FastAPI", kind: "required", category: "skill", verdict: "partial", priority: "high", priority_label: "High-priority preparation area", difficulty: "medium", why: "The job requires it and your profile shows only part of it." },
  { requirement_id: "r-py", text: "Python", kind: "required", category: "skill", verdict: "met", priority: "optional", priority_label: "Optional", difficulty: "easy", why: "Your profile already supports it, or it is a small extra." },
];

const ACTIONS: [string, string, string, "list" | "text"][] = [
  ["questions", "Interview questions", "Likely questions grouped by theme and difficulty, each tied to a requirement, with guidance built from your own evidence.", "list"],
  ["behavioral", "Behavioral prompts", "Situation, task, action and result prompts, each pointing at something you have really done.", "list"],
  ["technical", "Technical concepts", "The concepts this role is likely to test, explained briefly, with what you can already point to.", "list"],
  ["outreach", "Outreach message", "A short message to someone at the company, in your voice. You send it.", "text"],
  ["referral", "Referral request", "A short message asking someone you know for a referral. You send it.", "text"],
];

const ISO = (d: Date) => d.toISOString().slice(0, 10);

function planFor(date: string | null) {
  if (!date) return [];
  const start = new Date(); start.setUTCHours(0, 0, 0, 0);
  const end = new Date(`${date}T00:00:00Z`);
  const days = Math.max(1, Math.round((end.getTime() - start.getTime()) / 86400000) + 1);
  if (days === 1) return [{ date: ISO(start), kind: "review", topics: ["Experience with AWS"] }];
  const out = [];
  for (let i = 0; i < days - 2; i += 1) out.push({ date: ISO(new Date(start.getTime() + i * 86400000)), kind: i < Math.max(1, (days - 2) / 2) ? "learn" : "practise", topics: i === 0 ? ["Experience with AWS", "Building REST APIs with FastAPI"] : [] });
  out.push({ date: ISO(new Date(start.getTime() + (days - 2) * 86400000)), kind: "review", topics: ["Experience with AWS"] });
  out.push({ date: ISO(new Date(start.getTime() + (days - 1) * 86400000)), kind: "mock", topics: [] });
  return out;
}

function itemsFor(action: string, invented: boolean) {
  const make = (i: number, text: string, guidance: string, evidence: number) => ({
    key: `item:${action}:${i}`, text, guidance, category: i === 0 ? "Experience" : "Learning", difficulty: i === 0 ? "medium" : "easy",
    requirement_id: i === 0 ? "r-api" : "r-aws", evidence_count: evidence, insufficient_evidence: evidence === 0,
    note: evidence === 0 ? "Your profile does not currently contain enough evidence to answer this confidently. Add what you have done, or use this to decide what to learn." : "",
    claims: i === 0 && invented ? [{ text: "Kubernetes", kind: "name", supported: false, source: null }] : [], unsupported_count: i === 0 && invented ? 1 : 0, done: false,
  });
  return [make(0, "Tell me about your work with FastAPI.", "Use the Kestrel Analytics project where you wrote the API.", 1), make(1, "How would you approach AWS if you had not used it?", "Start with the basic services and build something small.", 0)];
}

export function handlePreparation(path: string, method: string, body: unknown, fake: { prep: FakePrep }): { status: number; json?: unknown } | null {
  const m = path.match(/^\/api\/v1\/jobs\/([^/]+)\/preparation(\/.*)?$/);
  if (!m) return null;
  const rest = m[2] ?? "";
  const p = fake.prep;
  const b = (body ?? {}) as Record<string, unknown>;
  const reply = () => ({ status: 200, json: view(m[1]!, p) });

  if (method === "GET" && rest === "") {
    for (const o of Object.values(p.outputs)) {
      if (o.status === "queued" || o.status === "working") {
        o.reads += 1;
        if (o.reads >= 2) {
          if (p.failWith) { o.status = "failed"; o.error = p.failWith; } else o.status = "ready";
        }
      }
    }
    return reply();
  }
  const out = rest.match(/^\/outputs\/([^/?]+)$/);
  if (out) {
    const action = out[1]!;
    if (!ACTIONS.some((a) => a[0] === action)) return { status: 404, json: { code: "NOT_FOUND", message: "Not found." } };
    if (method === "POST") {
      p.calls.push(`start:${action}`);
      if (!p.can_prepare) return { status: 409, json: { code: "ANALYSIS_NEEDED", message: "Check this job against your evidence first. Preparation is built from what the check found." } };
      const existing = p.outputs[action];
      if (existing && (existing.status === "queued" || existing.status === "working")) return { status: 409, json: { code: "PREPARATION_IN_PROGRESS", message: "This is already being written." } };
      const replace = (b as { __replace?: boolean }).__replace === true;
      if (existing && existing.origin === "edited" && !replace) return { status: 409, json: { code: "EDITED_TEXT", message: "You edited this text. Writing it again replaces your edits. Confirm to go ahead." } };
      p.outputs[action] = { status: "queued", reads: 0, origin: "model", body: `I worked with this in my internship: Wrote the API with FastAPI at Kestrel Analytics.${p.invented ? " I also run Kubernetes for 400 users." : ""}`, error: null, unsupported: p.invented ? ["Kubernetes"] : [] };
      return { status: 202, json: view(m[1]!, p) };
    }
    if (method === "PUT") {
      const text = String(b.text ?? "");
      const o = p.outputs[action];
      if (!o || o.status !== "ready" || !["outreach", "referral"].includes(action)) return { status: 404, json: { code: "NOT_FOUND", message: "Not found." } };
      if (text.trim().length < 40) return { status: 422, json: { code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: { text: "Write between 40 and 1200 characters." } } };
      o.body = text; o.origin = "edited"; o.unsupported = /kubernetes|google/i.test(text) ? ["Kubernetes"] : [];
      return reply();
    }
  }
  if (method === "PUT" && rest === "/date") {
    const date = (b.interview_date as string | null) ?? null;
    if (date && date < ISO(new Date())) return { status: 422, json: { code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: { interview_date: "Choose today or a day after it." } } };
    p.date = date; return reply();
  }
  if (method === "PUT" && rest === "/company") {
    const link = String(b.link ?? "").trim();
    if (link && !/^https?:\/\//.test(link)) return { status: 422, json: { code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: { link: "Use an address that starts with https://. It is kept for you to open. It is never fetched." } } };
    p.company = { link, notes: String(b.notes ?? "") }; return reply();
  }
  if (method === "PUT" && rest === "/progress") {
    const key = String(b.key ?? "");
    if (!/^(concept|item):/.test(key)) return { status: 422, json: { code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: { key: "That is not something that can be ticked." } } };
    p.done = b.done ? [...new Set([...p.done, key])] : p.done.filter((k) => k !== key); return reply();
  }
  if (method === "POST" && rest === "/mock") {
    p.calls.push("mock:start");
    if (!p.can_prepare) return { status: 409, json: { code: "ANALYSIS_NEEDED", message: "Check this job against your evidence first. Preparation is built from what the check found." } };
    p.mock = { id: "mock-1", state: "active", turns: [], questions: ['The posting asks for: "Experience with AWS". If you were asked about this, how would you approach learning it, and what related work could you point to?', 'The posting asks for: "Building REST APIs with FastAPI". Tell me what you have done toward this and where you are still building.'] };
    return { status: 201, json: view(m[1]!, p) };
  }
  const mock = rest.match(/^\/mock\/([^/]+)\/(answer|finish)$/);
  if (mock && p.mock && p.mock.id === mock[1]) {
    if (mock[2] === "finish") { p.mock.state = "finished"; return reply(); }
    if (p.mock.state !== "active") return { status: 409, json: { code: "MOCK_FINISHED", message: "This practice interview is finished. Start a new one." } };
    const answer = String(b.answer ?? "").trim();
    if (answer.length < 20) return { status: 422, json: { code: "VALIDATION_FAILED", message: "Some details need fixing.", fields: { answer: "Write your answer in a few sentences, as you would say it." } } };
    const bad = /kubernetes|google/i.test(answer);
    p.mock.turns.push({ question: p.mock.questions[p.mock.turns.length]!, answer, words: answer.split(/\s+/).length, total: bad ? 9 : 11, maximum: 12,
      rubric: [{ name: "Structure", score: 3, note: "Clear: situation, action and result are all there." }, { name: "Specifics", score: 3, note: "Specific: it has numbers and real names in it." }, { name: "Relevance", score: 3, note: "It speaks to what the posting asks." }, { name: "Honesty", score: bad ? 0 : 2, note: bad ? "These are not in your profile: Kubernetes, Google. Add them to your profile if true, or take them out." : "Everything specific in it is in your profile." }],
      unsupported_claims: bad ? ["Kubernetes", "Google"] : [], follow_up: p.mock.turns.length + 1 < p.mock.questions.length ? "Next, practise this one: Building REST APIs with FastAPI" : "You have been through every topic. Repeat the weakest answer, aiming for a number and a result." });
    if (p.mock.turns.length >= p.mock.questions.length) p.mock.state = "finished";
    return reply();
  }
  return { status: 404, json: { code: "NOT_FOUND", message: "Not found." } };
}

function view(jobId: string, p: FakePrep) {
  const readyItems = ACTIONS.filter((a) => a[3] === "list" && p.outputs[a[0]]?.status === "ready").flatMap((a) => itemsFor(a[0], p.invented));
  const keys = [...CONCEPTS.filter((c) => c.priority !== "optional").map((c) => `concept:${c.requirement_id}`), ...readyItems.map((i) => i.key)];
  const done = keys.filter((k) => p.done.includes(k)).length;
  const mock = p.mock;
  return {
    job_id: jobId, title: "Backend Engineer", company: "Kestrel Analytics", can_prepare: p.can_prepare,
    blocker: p.can_prepare ? null : "Check this job against your evidence first. Preparation is built from what the check found.",
    family: "software", years: 3, rules_version: "prep-rules-1",
    coverage: { required: 3, met: 1, partial: 1, not_shown: 1, unchecked: 0 },
    concepts: CONCEPTS.map((c) => ({ ...c, key: `concept:${c.requirement_id}`, done: p.done.includes(`concept:${c.requirement_id}`) })),
    actions: ACTIONS.map(([key, label, description, shape]) => {
      const o = p.outputs[key];
      const ready = o?.status === "ready";
      return {
        key, label, description, shape, status: o?.status ?? null, error: o?.status === "failed" ? o.error : null, origin: o?.origin ?? null,
        items: ready && shape === "list" ? itemsFor(key, p.invented).map((i) => ({ ...i, done: p.done.includes(i.key) })) : [],
        body: ready && shape === "text" ? o.body : "", word_count: ready && shape === "text" ? o.body.split(/\s+/).length : 0,
        claims: ready && shape === "text" ? o.unsupported.map((t) => ({ text: t, kind: "name", supported: false, source: null })) : [],
        evidence: ready ? [{ text: "Wrote the API with FastAPI at Kestrel Analytics.", source: "profile", cited: true }] : [], updated_at: o ? "2026-11-05T10:00:00Z" : null,
      };
    }),
    interview_date: p.date, plan: planFor(p.date),
    company_info: { name: "Kestrel Analytics", location: "Bengaluru", source_name: "LinkedIn", source_url: "https://example.com/jobs/1", link: p.company.link, notes: p.company.notes, says: ["Place: Bengaluru", "Work arrangement: hybrid"] },
    progress: { done, total: keys.length, percent: keys.length ? Math.round((100 * done) / keys.length) : 0 },
    mock: mock ? { id: mock.id, state: mock.state, question_count: mock.questions.length, turns: mock.turns, current_question: mock.state === "active" ? mock.questions[mock.turns.length] ?? null : null, current_index: mock.turns.length } : null,
    likely_label: "Likely questions, based on this job description. They are preparation, not a prediction of what will be asked.",
    generated_label: "Written for you from your own evidence. Check every line. Anything it says about you that is not in your evidence is listed beside it.",
  };
}
