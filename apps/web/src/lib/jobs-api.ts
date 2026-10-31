import { request } from "./api";
import type { EligibilityState, JobUiState } from "./states";

/** Where a person says a posting came from. The server stores the label they choose. */
export const SOURCE_NAMES = [
  "LinkedIn",
  "Wellfound",
  "Indeed",
  "Naukri",
  "Internshala",
  "Company career page",
  "Message or referral",
  "Other",
] as const;

export const POSTING_MIN_CHARS = 100;
export const POSTING_MAX_CHARS = 20_000;

export interface JobSummary {
  id: string;
  title: string | null;
  company: string | null;
  source_name: string;
  /** How the text reached us. "user_paste" means the person pasted it. */
  acquisition_method: string;
  ui_state: JobUiState;
  can_retry: boolean;
  error_message: string | null;
  eligibility: EligibilityState | null;
  work_mode: string | null;
  location: string | null;
  requirement_count: number;
  created_at: string;
}

export interface JobFact {
  value: string | number | string[];
  /** The posting's own words behind the fact. */
  quote: string;
}

export interface JobGate {
  gate: string;
  label: string;
  state: EligibilityState;
  reason: string;
  posting_quote: string | null;
}

export interface JobRequirement {
  id: string;
  ordinal: number;
  text: string;
  kind: "required" | "preferred";
  category: string;
  years_min: number | null;
  quote: string;
  quote_start: number;
  quote_end: number;
}

export interface JobDetail extends JobSummary {
  source_url: string | null;
  visibility: string;
  facts: Record<string, JobFact>;
  requirements: JobRequirement[];
  eligibility_detail: { state: EligibilityState; rules_version: string; gates: JobGate[] } | null;
  facts_dropped: number;
  requirements_dropped: number;
  prompt_version: string | null;
  run_id: string | null;
  extracted_at: string | null;
  text: string;
}

export interface PasteResult {
  job: JobDetail;
  /** True when this exact posting was pasted before. Nothing was read again. */
  duplicate: boolean;
}

const BASE = "/api/v1/jobs";

export function fetchJobs(signal?: AbortSignal): Promise<JobSummary[]> {
  return request<JobSummary[]>("GET", BASE, { signal });
}

export function fetchJob(id: string, signal?: AbortSignal): Promise<JobDetail> {
  return request<JobDetail>("GET", `${BASE}/${encodeURIComponent(id)}`, { signal });
}

export function pasteJob(input: { source_name: string; source_url: string | null; text: string }): Promise<PasteResult> {
  return request<PasteResult>("POST", BASE, { body: input });
}

export function reanalyzeJob(id: string): Promise<JobDetail> {
  return request<JobDetail>("POST", `${BASE}/${encodeURIComponent(id)}/reanalyze`);
}

export function deleteJob(id: string): Promise<void> {
  return request<void>("DELETE", `${BASE}/${encodeURIComponent(id)}`);
}
