import { request } from "./api";

export type Mark = "bold" | "italic" | "underline" | "highlight";

export interface RichNode {
  type: string;
  text?: string;
  marks?: { type: Mark }[];
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
