import { request } from "./api";
import type { PasteResult } from "./jobs-api";
import type { Band, EligibilityState } from "./states";

export const DECISION_STATES = ["new", "saved", "dismissed", "approved_for_prep", "applied", "archived"] as const;
export type DecisionState = (typeof DECISION_STATES)[number];

export type DecisionAction =
  | "save"
  | "unsave"
  | "dismiss"
  | "undo_dismiss"
  | "approve"
  | "mark_applied"
  | "undo_applied"
  | "archive";

export interface Decision {
  state: DecisionState;
  state_label: string;
  /** What the server offers now, in the order to show them. The browser never decides this. */
  actions: { action: DecisionAction; label: string }[];
  note: string;
  applied_at: string | null;
  updated_at: string | null;
}

export interface DecisionResult {
  decision: Decision;
  /** The action that takes this one back, when it can be taken back. */
  undo: DecisionAction | null;
  undo_label: string | null;
}

export interface WorkRow {
  id: string;
  title: string | null;
  company: string | null;
  source_name: string;
  acquisition_method: string;
  work_mode: string | null;
  location: string | null;
  employment_type: string | null;
  seniority: string | null;
  eligibility: EligibilityState | null;
  band: Band | null;
  reading: "reading" | "ready" | "failed";
  decision: Decision;
  has_note: boolean;
  created_at: string;
}

export interface Facets {
  views: Record<string, number>;
  work_modes: Record<string, number>;
  eligibility: Record<string, number>;
  bands: Record<string, number>;
  employment_types: Record<string, number>;
  seniorities: Record<string, number>;
  sources: Record<string, number>;
}

export interface Workbench {
  rows: WorkRow[];
  total: number;
  query: Record<string, unknown>;
  facets: Facets;
  truncated: boolean;
}

export const VIEWS = ["active", "saved", "applications", "dismissed", "archived", "all"] as const;
export type View = (typeof VIEWS)[number];

export const VIEW_LABELS: Record<View, string> = {
  active: "Active",
  saved: "Saved",
  applications: "Applications",
  dismissed: "Dismissed",
  archived: "Archived",
  all: "All",
};

export const SORTS = ["added", "title", "company", "fit", "eligibility", "applied"] as const;
export type Sort = (typeof SORTS)[number];

export const SORT_LABELS: Record<Sort, string> = {
  added: "Date added",
  title: "Job title",
  company: "Company",
  fit: "Fit",
  eligibility: "Eligibility",
  applied: "Date applied",
};

/** The list the person is looking at. Every part of it lives in the address, so back, reload and
 * sharing a link all work. The server cleans it, so unknown values are harmless. */
export interface Query {
  view: View;
  q: string;
  work_mode: string[];
  eligibility: string[];
  band: string[];
  employment_type: string[];
  seniority: string[];
  source: string[];
  company: string;
  location: string;
  sort: Sort;
  /** true or false when the person chose a direction. null means the natural one for the sort. */
  desc: boolean | null;
}

export const EMPTY_QUERY: Query = {
  view: "active",
  q: "",
  work_mode: [],
  eligibility: [],
  band: [],
  employment_type: [],
  seniority: [],
  source: [],
  company: "",
  location: "",
  sort: "added",
  desc: null,
};

const LISTS = ["work_mode", "eligibility", "band", "employment_type", "seniority", "source"] as const;

export function queryToParams(query: Query): URLSearchParams {
  const params = new URLSearchParams();
  if (query.view !== "active") params.set("view", query.view);
  if (query.q) params.set("q", query.q);
  for (const key of LISTS) for (const value of query[key]) params.append(key, value);
  if (query.company) params.set("company", query.company);
  if (query.location) params.set("location", query.location);
  if (query.sort !== "added") params.set("sort", query.sort);
  if (query.desc !== null) params.set("desc", String(query.desc));
  return params;
}

export function paramsToQuery(params: URLSearchParams): Query {
  const view = params.get("view");
  const sort = params.get("sort");
  const desc = params.get("desc");
  return {
    view: VIEWS.find((v) => v === view) ?? "active",
    q: params.get("q") ?? "",
    work_mode: params.getAll("work_mode"),
    eligibility: params.getAll("eligibility"),
    band: params.getAll("band"),
    employment_type: params.getAll("employment_type"),
    seniority: params.getAll("seniority"),
    source: params.getAll("source"),
    company: params.get("company") ?? "",
    location: params.get("location") ?? "",
    sort: SORTS.find((s) => s === sort) ?? "added",
    desc: desc === "true" ? true : desc === "false" ? false : null,
  };
}

/** How many filters (apart from the view and the sort) are set. */
export function activeFilterCount(query: Query): number {
  return (
    LISTS.reduce((sum, key) => sum + query[key].length, 0) + (query.company ? 1 : 0) + (query.location ? 1 : 0)
  );
}

/** A stored view is the server's cleaned form of a query. Turn it back into the address form. */
export function storedToQuery(stored: Record<string, unknown>): Query {
  const list = (key: string): string[] => (Array.isArray(stored[key]) ? (stored[key] as string[]) : []);
  const text = (key: string): string => (typeof stored[key] === "string" ? (stored[key] as string) : "");
  const view = stored.view;
  const sort = stored.sort;
  return {
    view: VIEWS.find((v) => v === view) ?? "active",
    q: text("text"),
    work_mode: list("work_modes"),
    eligibility: list("eligibility"),
    band: list("bands"),
    employment_type: list("employment_types"),
    seniority: list("seniorities"),
    source: list("sources"),
    company: text("company"),
    location: text("location"),
    sort: SORTS.find((s) => s === sort) ?? "added",
    desc: typeof stored.descending === "boolean" ? stored.descending : null,
  };
}

/** The query in the shape the server stores for a saved view. */
export function queryToStored(query: Query): Record<string, unknown> {
  const out: Record<string, unknown> = { view: query.view, sort: query.sort };
  if (query.desc !== null) out.descending = query.desc;
  if (query.q) out.text = query.q;
  if (query.company) out.company = query.company;
  if (query.location) out.location = query.location;
  const map: [keyof Query, string][] = [
    ["work_mode", "work_modes"],
    ["eligibility", "eligibility"],
    ["band", "bands"],
    ["employment_type", "employment_types"],
    ["seniority", "seniorities"],
    ["source", "sources"],
  ];
  for (const [from, to] of map) {
    const values = query[from] as string[];
    if (values.length > 0) out[to] = values;
  }
  return out;
}

export function fetchWorkbench(query: Query, signal?: AbortSignal): Promise<Workbench> {
  const qs = queryToParams(query).toString();
  return request<Workbench>("GET", `/api/v1/workbench${qs ? `?${qs}` : ""}`, { signal });
}

export function decideJob(id: string, action: DecisionAction, appliedOn?: string): Promise<DecisionResult> {
  return request<DecisionResult>("POST", `/api/v1/jobs/${encodeURIComponent(id)}/decision`, {
    body: appliedOn ? { action, applied_on: appliedOn } : { action },
  });
}

export function saveNote(id: string, note: string): Promise<Decision> {
  return request<Decision>("PUT", `/api/v1/jobs/${encodeURIComponent(id)}/note`, { body: { note } });
}

export interface BulkResult {
  results: { id: string; ok: boolean; state: string | null; message: string | null }[];
  done: number;
  skipped: number;
  undo: DecisionAction | null;
  undo_label: string | null;
}

export function bulkDecide(ids: string[], action: DecisionAction): Promise<BulkResult> {
  return request<BulkResult>("POST", "/api/v1/workbench/bulk", { body: { ids, action } });
}

export interface SavedView {
  id: string;
  name: string;
  query: Record<string, unknown>;
  created_at: string;
}

export function fetchViews(signal?: AbortSignal): Promise<SavedView[]> {
  return request<SavedView[]>("GET", "/api/v1/workbench/views", { signal });
}

export function saveView(name: string, query: Query): Promise<SavedView> {
  return request<SavedView>("POST", "/api/v1/workbench/views", { body: { name, query: queryToStored(query) } });
}

export function deleteView(id: string): Promise<void> {
  return request<void>("DELETE", `/api/v1/workbench/views/${encodeURIComponent(id)}`);
}

/** Make a private posting from a job found on a permitted source. */
export function addToMyJobs(sourceJobId: string): Promise<PasteResult> {
  return request<PasteResult>("POST", `/api/v1/search/jobs/${encodeURIComponent(sourceJobId)}/add`);
}

export const WORK_MODE_LABELS: Record<string, string> = { remote: "Remote", hybrid: "Hybrid", onsite: "On-site" };
export const EMPLOYMENT_LABELS: Record<string, string> = {
  full_time: "Full time",
  part_time: "Part time",
  internship: "Internship",
  contract: "Contract",
  freelance: "Freelance",
};
export const SENIORITY_LABELS: Record<string, string> = {
  intern: "Intern",
  entry: "Entry level",
  mid: "Mid level",
  senior: "Senior",
  lead: "Lead",
};

/** The tone of a decision state, for the dot beside its label. The label carries the meaning. */
export function decisionTone(state: DecisionState): "ok" | "warn" | "danger" | "neutral" {
  if (state === "applied" || state === "approved_for_prep") return "ok";
  if (state === "saved") return "neutral";
  if (state === "dismissed") return "warn";
  return "neutral";
}

/** What an action does, in one plain sentence. Shown beside the button that does it. */
export const ACTION_HELP: Record<DecisionAction, string> = {
  save: "Keep it on your Saved list.",
  unsave: "Take it off your Saved list.",
  dismiss: "Hide it from your active list. You can undo this.",
  undo_dismiss: "Bring it back to your active list.",
  approve: "Mark it as one you want to prepare materials for. Preparation arrives in a later step.",
  mark_applied: "Record that you applied on the employer's site. This product never applies for you.",
  undo_applied: "Take the applied record back.",
  archive: "Move it out of the way. Archived jobs stay under Archived.",
};
