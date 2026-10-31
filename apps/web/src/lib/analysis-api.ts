import { request } from "./api";
import type { AnalysisUiState, Band, Verdict } from "./states";

export interface Citation {
  chunk_id: string;
  quote: string;
  source: "profile" | "answer";
  entry_type: string | null;
  /** The entry was edited or removed after the check, so the quote may be out of date. */
  changed: boolean;
}

export interface VerdictRow {
  requirement_id: string;
  requirement: string;
  kind: "required" | "preferred";
  category: string;
  posting_quote: string;
  verdict: Verdict | null;
  evidence_kind: "direct" | "inferred" | null;
  confidence: "high" | "medium" | "none" | null;
  citations: Citation[];
  reason: string;
  capped: boolean;
  feedback: "right" | "wrong" | null;
}

export interface Question {
  id: string;
  requirement_id: string;
  requirement: string;
  question: string;
  status: "pending" | "answered" | "skipped";
  answer: string | null;
}

export interface Gap {
  requirement_id: string;
  requirement: string;
  state: string;
  proof_needed: string;
  next_step: string;
}

export interface Score {
  scoring_version: string;
  band: Band;
  required_total: number;
  met: number;
  partial: number;
  conflicting: number;
  not_verified: number;
  preferred_total: number;
  preferred_supported: number;
  reasons: string[];
}

export interface Analysis {
  ui_state: AnalysisUiState;
  can_start: boolean;
  blocker: string | null;
  error_message: string | null;
  checked: number;
  total: number;
  score: Score | null;
  verdicts: VerdictRow[];
  gate_requirements: { requirement_id: string; requirement: string; kind: "required" | "preferred" }[];
  questions: Question[];
  gaps: Gap[];
  stale: boolean;
  recommendation_feedback: "right" | "wrong" | null;
  scoring_version: string;
  prompt_version: string | null;
}

const base = (jobId: string) => `/api/v1/jobs/${encodeURIComponent(jobId)}/analysis`;

export function fetchAnalysis(jobId: string, signal?: AbortSignal): Promise<Analysis> {
  return request<Analysis>("GET", base(jobId), { signal });
}

export function startAnalysis(jobId: string): Promise<Analysis> {
  return request<Analysis>("POST", base(jobId));
}

export function answerQuestion(jobId: string, questionId: string, answer: string): Promise<Analysis> {
  return request<Analysis>("POST", `${base(jobId)}/questions/${encodeURIComponent(questionId)}/answer`, {
    body: { answer },
  });
}

export function skipQuestion(jobId: string, questionId: string): Promise<Analysis> {
  return request<Analysis>("POST", `${base(jobId)}/questions/${encodeURIComponent(questionId)}/skip`);
}

export function giveFeedback(
  jobId: string,
  input: { requirement_id: string | null; answer: "right" | "wrong" },
): Promise<Analysis> {
  return request<Analysis>("POST", `${base(jobId)}/feedback`, { body: input });
}
