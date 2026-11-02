import { request } from "./api";

export interface SourceDecision {
  key: string;
  display_name: string;
  outcome: "search" | "import_required" | "unavailable";
  message: string;
  reason: string | null;
  import_available: boolean;
  named_by_person: boolean;
  notes: string[];
}

export interface CompanyCandidate {
  key: string;
  name: string;
  score: number;
}

export interface CompanyDecision {
  query: string;
  status: "resolved" | "ambiguous" | "unknown";
  route: "first_party" | "aggregator" | "import" | "choose" | "none";
  message: string;
  company: CompanyCandidate | null;
  source_key: string | null;
  candidates: CompanyCandidate[];
}

export interface SearchPlan {
  interpreted_by: string;
  intent: Record<string, unknown>;
  headline: string;
  can_search_now: boolean;
  notes: string[];
  sources: SourceDecision[];
  companies: CompanyDecision[];
  authorization: { countries: string[]; needs_sponsorship: boolean | null; origin: string };
}

export interface SourceInfo {
  key: string;
  display_name: string;
  source_type: string;
  outcome: SourceDecision["outcome"];
  message: string;
  reason: string | null;
  import_available: boolean;
  compliance_status: "verified" | "unverified" | "restricted" | "prohibited";
  terms_checked_at: string | null;
  terms_url: string | null;
  attribution_text: string;
  health_status: "unknown" | "healthy" | "degraded" | "down";
  last_success_at: string | null;
  jobs_open: number;
}

export interface FetchedJob {
  id: string;
  title: string;
  company_name: string | null;
  location: string;
  workplace: string | null;
  employment_type: string | null;
  department: string;
  url: string;
  excerpt: string;
  source_key: string;
  source_name: string;
  attribution_text: string;
  posted_at: string | null;
  first_seen_at: string;
}

export interface IntentFields {
  roles?: string[];
  skills?: string[];
  locations?: string[];
  companies?: string[];
  work_mode?: string;
  sources?: string[];
}

export function fetchSources(signal?: AbortSignal): Promise<SourceInfo[]> {
  return request<SourceInfo[]>("GET", "/api/v1/search/sources", { signal });
}

export function planSearch(input: { query: string } | { intent: IntentFields }): Promise<SearchPlan> {
  return request<SearchPlan>("POST", "/api/v1/search/plan", { body: input });
}

export function fetchJobs(
  filters: { roles?: string[]; companies?: string[]; locations?: string[]; sources?: string[]; work_mode?: string },
  signal?: AbortSignal,
): Promise<FetchedJob[]> {
  const params = new URLSearchParams();
  for (const [name, values] of Object.entries(filters)) {
    for (const value of Array.isArray(values) ? values : values ? [values] : []) {
      if (value && !(name === "work_mode" && value === "any")) params.append(name, value);
    }
  }
  return request<FetchedJob[]>("GET", `/api/v1/search/jobs?${params.toString()}`, { signal });
}
