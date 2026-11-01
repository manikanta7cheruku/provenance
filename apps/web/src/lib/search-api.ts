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
