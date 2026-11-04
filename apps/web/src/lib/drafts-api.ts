import { request } from "./api";

export type DraftKind = "cover_note" | "answer";

export interface DraftClaim {
  text: string;
  kind: string;
  supported: boolean;
  source: string | null;
}

export interface DraftEvidence {
  text: string;
  source: string;
  cited: boolean;
}

export interface Draft {
  id: string;
  kind: DraftKind;
  question: string;
  body: string;
  ui_state: "working" | "ready" | "failed";
  origin: "model" | "edited";
  error_message: string | null;
  claims: DraftClaim[];
  unsupported_count: number;
  word_count: number;
  evidence: DraftEvidence[];
  updated_at: string;
}

export interface Drafts {
  drafts: Draft[];
  can_write: boolean;
  blocker: string | null;
  questions: { key: string; text: string }[];
  max_drafts: number;
  /** Said every time a draft is shown: it is a draft, and nothing is sent anywhere. */
  label: string;
}

const base = (jobId: string) => `/api/v1/jobs/${encodeURIComponent(jobId)}/drafts`;

export function fetchDrafts(jobId: string, signal?: AbortSignal): Promise<Drafts> {
  return request<Drafts>("GET", base(jobId), { signal });
}

export function startDraft(jobId: string, kind: DraftKind, question = "", replace = false): Promise<Drafts> {
  return request<Drafts>("POST", base(jobId), { body: { kind, question, replace } });
}

export function saveDraft(jobId: string, draftId: string, body: string): Promise<Draft> {
  return request<Draft>("PUT", `${base(jobId)}/${encodeURIComponent(draftId)}`, { body: { body } });
}

export function deleteDraft(jobId: string, draftId: string): Promise<void> {
  return request<void>("DELETE", `${base(jobId)}/${encodeURIComponent(draftId)}`);
}

export function isWriting(drafts: Drafts | null): boolean {
  return drafts?.drafts.some((d) => d.ui_state === "working") ?? false;
}

/** The claims in a draft that are in neither the evidence nor the job heading, in the person's words. */
export function unsupportedClaims(draft: Pick<Draft, "claims">): string[] {
  return draft.claims.filter((c) => !c.supported).map((c) => c.text);
}

const KIND_WORDS: Record<string, string> = { number: "a number", name: "a name or tool", "job term": "a word the job asks for" };

export function describeClaimKind(kind: string): string {
  return KIND_WORDS[kind] ?? "a claim";
}
