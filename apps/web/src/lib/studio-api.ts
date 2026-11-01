import { request } from "./api";

export type Mark = "bold" | "italic" | "underline" | "highlight" | "link";

export interface RichNode {
  type: string;
  text?: string;
  marks?: { type: Mark; attrs?: { href: string } }[];
  content?: RichNode[];
}

export interface RichDoc {
  type: "doc";
  content: RichNode[];
}

export interface ResumeBlock {
  id: string;
  heading: string;
  subheading: string;
  dates: string;
  location: string;
  body: RichDoc | null;
}

export interface ResumeSection {
  id: string;
  kind: string;
  title: string;
  blocks: ResumeBlock[];
}

export interface ResumeStyle {
  template: string;
  font_pair: string;
  size: string;
  spacing: string;
  margins: string;
  accent: string;
  divider: string;
  paper: string;
}

export interface ResumeContent {
  version: number;
  style: ResumeStyle;
  header: { name: string; headline: string; contacts: string[] };
  sections: ResumeSection[];
}

export interface ResumeSummary {
  id: string;
  title: string;
  revision: number;
  template: string;
  updated_at: string;
}

/** The free canvas document (version 2). Its full shape lives with the canvas editor. */
export interface CanvasWire {
  version: 2;
  style: Record<string, unknown>;
  pages: unknown[];
}

export type StudioContent = ResumeContent | CanvasWire;

export interface ResumeDocument extends ResumeSummary {
  content: StudioContent;
}

export interface TemplateInfo {
  key: string;
  name: string;
  description: string;
  ats_safe: boolean;
}

export interface StudioOptions {
  templates: TemplateInfo[];
  font_pairs: { key: string; label: string }[];
  sizes: string[];
  spacings: string[];
  margins: string[];
  dividers: string[];
  papers: string[];
  section_kinds: string[];
  max_resumes: number;
}

export interface VersionInfo {
  id: string;
  revision: number;
  created_at: string;
}

export interface ExportInfo {
  id: string;
  revision: number;
  ui_state: "preparing" | "ready" | "failed";
  size_bytes: number | null;
  page_count: number | null;
  error_message: string | null;
  created_at: string;
}

const BASE = "/api/v1/studio";
const enc = encodeURIComponent;

export function fetchOptions(signal?: AbortSignal): Promise<StudioOptions> {
  return request<StudioOptions>("GET", `${BASE}/options`, { signal });
}

export function fetchResumes(signal?: AbortSignal): Promise<ResumeSummary[]> {
  return request<ResumeSummary[]>("GET", `${BASE}/resumes`, { signal });
}

export function fetchResume(id: string, signal?: AbortSignal): Promise<ResumeDocument> {
  return request<ResumeDocument>("GET", `${BASE}/resumes/${enc(id)}`, { signal });
}

export function createResume(input: { start: "profile" | "blank"; template: string }): Promise<ResumeDocument> {
  return request<ResumeDocument>("POST", `${BASE}/resumes`, { body: input });
}

export function saveResume(
  id: string,
  input: { content: object; revision: number; title?: string; checkpoint?: boolean },
): Promise<ResumeSummary> {
  return request<ResumeSummary>("PUT", `${BASE}/resumes/${enc(id)}`, { body: input });
}

export function previewResume(id: string, content: object, signal?: AbortSignal): Promise<{ html: string }> {
  return request<{ html: string }>("POST", `${BASE}/resumes/${enc(id)}/preview`, {
    body: { content },
    signal,
  });
}

export function fetchVersions(id: string, signal?: AbortSignal): Promise<VersionInfo[]> {
  return request<VersionInfo[]>("GET", `${BASE}/resumes/${enc(id)}/versions`, { signal });
}

export function restoreVersion(id: string, versionId: string, revision: number): Promise<ResumeDocument> {
  return request<ResumeDocument>("POST", `${BASE}/resumes/${enc(id)}/versions/${enc(versionId)}/restore`, {
    body: { revision },
  });
}

export function deleteResume(id: string): Promise<void> {
  return request<void>("DELETE", `${BASE}/resumes/${enc(id)}`);
}

export function fetchExports(id: string, signal?: AbortSignal): Promise<ExportInfo[]> {
  return request<ExportInfo[]>("GET", `${BASE}/resumes/${enc(id)}/exports`, { signal });
}

export function startExport(id: string): Promise<ExportInfo> {
  return request<ExportInfo>("POST", `${BASE}/resumes/${enc(id)}/exports`);
}

export function downloadUrl(exportId: string): string {
  return `${BASE}/exports/${enc(exportId)}/download`;
}

// ---- tailoring a resume to a job (checkpoint 2.4)

export interface TailorJob {
  job_id: string;
  title: string | null;
  company: string | null;
}

export interface TailorClaim {
  text: string;
  kind: string;
  supported: boolean;
  source: string | null;
}

export interface TailorSuggestion {
  id: string;
  unit_id: string;
  kind: "bullets" | "paragraph";
  label: string;
  before_lines: string[];
  after_lines: string[];
  reason: string;
  requirements: { id: string; text: string }[];
  citations: { chunk_id: string; quote: string; source: string; entry_type: string | null }[];
  claims: TailorClaim[];
  blocked: boolean;
  edited: boolean;
  status: "pending" | "accepted" | "rejected";
}

export interface Tailoring {
  id: string;
  job_id: string;
  job_title: string | null;
  company: string | null;
  ui_state: "working" | "ready" | "failed";
  error_message: string | null;
  suggestions: TailorSuggestion[];
  unclaimed: { text: string; reason: string }[];
}

export function fetchTailorJobs(signal?: AbortSignal): Promise<TailorJob[]> {
  return request<TailorJob[]>("GET", `${BASE}/tailoring/jobs`, { signal });
}

export function startTailoring(resumeId: string, jobId: string): Promise<Tailoring> {
  return request<Tailoring>("POST", `${BASE}/resumes/${enc(resumeId)}/tailoring`, { body: { job_id: jobId } });
}

export function fetchTailoring(resumeId: string, jobId: string, signal?: AbortSignal): Promise<Tailoring | null> {
  return request<Tailoring | null>("GET", `${BASE}/resumes/${enc(resumeId)}/tailoring?job_id=${enc(jobId)}`, { signal });
}

const suggestionUrl = (resumeId: string, tailoringId: string, suggestionId: string) =>
  `${BASE}/resumes/${enc(resumeId)}/tailoring/${enc(tailoringId)}/suggestions/${enc(suggestionId)}`;

export function editSuggestion(resumeId: string, tailoringId: string, id: string, afterLines: string[]): Promise<TailorSuggestion> {
  return request<TailorSuggestion>("PUT", suggestionUrl(resumeId, tailoringId, id), { body: { after_lines: afterLines } });
}

export function acceptSuggestion(
  resumeId: string,
  tailoringId: string,
  id: string,
  revision: number,
): Promise<{ suggestion: TailorSuggestion; document: ResumeSummary }> {
  return request("POST", `${suggestionUrl(resumeId, tailoringId, id)}/accept`, { body: { revision } });
}

export function rejectSuggestion(resumeId: string, tailoringId: string, id: string): Promise<TailorSuggestion> {
  return request<TailorSuggestion>("POST", `${suggestionUrl(resumeId, tailoringId, id)}/reject`);
}
