import { request } from "./api";
import type { UiState } from "./states";

export interface RunSummary {
  id: string;
  workflow_type: string;
  workflow_label: string;
  ui_state: UiState;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface RunList {
  items: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface RunStep {
  ordinal: number;
  step_name: string;
  ui_state: UiState;
  duration_ms: number | null;
  error_summary: string | null;
}

export interface LlmCall {
  purpose: string;
  provider: string;
  model: string;
  prompt_version: string | null;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  latency_ms: number;
  status: string;
}

export interface RunDetail {
  run: RunSummary;
  error_summary: string | null;
  steps: RunStep[];
  llm_calls: LlmCall[];
}

export function fetchRuns(offset: number, signal?: AbortSignal): Promise<RunList> {
  return request<RunList>("GET", `/api/v1/runs?limit=25&offset=${offset}`, { signal });
}

export function fetchRun(id: string, signal?: AbortSignal): Promise<RunDetail> {
  return request<RunDetail>("GET", `/api/v1/runs/${encodeURIComponent(id)}`, { signal });
}
