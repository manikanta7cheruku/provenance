import { request } from "./api";

export interface PrepClaim {
  text: string;
  kind: string;
  supported: boolean;
  source: string | null;
}

export interface PrepItem {
  key: string;
  text: string;
  guidance: string;
  category: string;
  difficulty: string;
  requirement_id: string | null;
  evidence_count: number;
  insufficient_evidence: boolean;
  note: string;
  claims: PrepClaim[];
  unsupported_count: number;
  done: boolean;
}

export type OutputStatus = "queued" | "working" | "ready" | "failed";

export interface PrepAction {
  key: string;
  label: string;
  description: string;
  shape: "list" | "text";
  status: OutputStatus | null;
  error: string | null;
  origin: "model" | "edited" | null;
  items: PrepItem[];
  body: string;
  word_count: number;
  claims: PrepClaim[];
  evidence: { text: string; source: string; cited: boolean }[];
  updated_at: string | null;
}

export interface PrepConcept {
  key: string;
  requirement_id: string;
  text: string;
  kind: string;
  category: string;
  verdict: string;
  priority: "critical" | "high" | "useful" | "optional";
  priority_label: string;
  difficulty: string;
  why: string;
  done: boolean;
}

export interface MockRubric {
  name: string;
  score: number;
  note: string;
}

export interface MockTurn {
  question: string;
  answer: string;
  rubric: MockRubric[];
  total: number;
  maximum: number;
  unsupported_claims: string[];
  follow_up: string;
  words: number;
}

export interface Mock {
  id: string;
  state: "active" | "finished";
  question_count: number;
  turns: MockTurn[];
  current_question: string | null;
  current_index: number;
}

export interface Preparation {
  job_id: string;
  title: string;
  company: string;
  can_prepare: boolean;
  blocker: string | null;
  family: string;
  years: number;
  rules_version: string;
  coverage: {
    required: number;
    met: number;
    partial: number;
    not_shown: number;
    unchecked: number;
  };
  concepts: PrepConcept[];
  actions: PrepAction[];
  interview_date: string | null;
  plan: { date: string; kind: string; topics: string[] }[];
  company_info: {
    name: string;
    location: string;
    source_name: string;
    source_url: string | null;
    link: string;
    notes: string;
    says: string[];
  };
  progress: { done: number; total: number; percent: number };
  mock: Mock | null;
  likely_label: string;
  generated_label: string;
}

const base = (jobId: string) =>
  `/api/v1/jobs/${encodeURIComponent(jobId)}/preparation`;

export function fetchPreparation(
  jobId: string,
  signal?: AbortSignal,
): Promise<Preparation> {
  return request<Preparation>("GET", base(jobId), { signal });
}

export function startOutput(
  jobId: string,
  action: string,
  replace = false,
): Promise<Preparation> {
  return request<Preparation>(
    "POST",
    `${base(jobId)}/outputs/${encodeURIComponent(action)}${replace ? "?replace=true" : ""}`,
  );
}

export function saveMessage(
  jobId: string,
  action: string,
  text: string,
): Promise<Preparation> {
  return request<Preparation>(
    "PUT",
    `${base(jobId)}/outputs/${encodeURIComponent(action)}`,
    { body: { text } },
  );
}

export function setInterviewDate(
  jobId: string,
  date: string | null,
): Promise<Preparation> {
  return request<Preparation>("PUT", `${base(jobId)}/date`, {
    body: { interview_date: date },
  });
}

export function saveCompany(
  jobId: string,
  link: string,
  notes: string,
): Promise<Preparation> {
  return request<Preparation>("PUT", `${base(jobId)}/company`, {
    body: { link, notes },
  });
}

export function tick(
  jobId: string,
  key: string,
  done: boolean,
): Promise<Preparation> {
  return request<Preparation>("PUT", `${base(jobId)}/progress`, {
    body: { key, done },
  });
}

export function startMock(jobId: string): Promise<Preparation> {
  return request<Preparation>("POST", `${base(jobId)}/mock`);
}

export function answerMock(
  jobId: string,
  mockId: string,
  answer: string,
): Promise<Preparation> {
  return request<Preparation>(
    "POST",
    `${base(jobId)}/mock/${encodeURIComponent(mockId)}/answer`,
    { body: { answer } },
  );
}

export function finishMock(
  jobId: string,
  mockId: string,
): Promise<Preparation> {
  return request<Preparation>(
    "POST",
    `${base(jobId)}/mock/${encodeURIComponent(mockId)}/finish`,
  );
}

/** Whether any piece of material is still being written, so the screen keeps looking. */
export function isWriting(preparation: Preparation): boolean {
  return preparation.actions.some(
    (a) => a.status === "queued" || a.status === "working",
  );
}

export const PRIORITY_ORDER = [
  "critical",
  "high",
  "useful",
  "optional",
] as const;

export const VERDICT_WORDS: Record<string, string> = {
  met: "Your profile shows this",
  partial: "Your profile shows part of this",
  not_verified: "Your profile does not show this yet",
  conflicting: "Your profile disagrees with itself here",
  unchecked: "Not checked yet",
};

export const PLAN_KIND_WORDS: Record<string, string> = {
  learn: "Learn",
  practise: "Practise",
  review: "Review",
  mock: "Mock interview",
};
