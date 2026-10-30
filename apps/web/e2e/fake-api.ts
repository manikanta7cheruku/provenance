// A small stateful fake of the API for browser tests of the profile screen.
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

export interface Fake { resume: ReturnType<typeof resumeBody> | null; entries: Entry[]; reads: number; prefs: Record<string, unknown>; nextId: number }

export async function fakeApi(page: Page, initial: Partial<Fake> = {}): Promise<Fake> {
  const fake: Fake = {
    resume: null, entries: [], reads: 0, nextId: 10, prefs: {
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
    return json({ code: "NOT_FOUND", message: "not mocked" }, 404);
  });
  return fake;
}

