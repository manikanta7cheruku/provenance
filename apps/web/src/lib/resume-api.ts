import { request, uploadFile } from "./api";
import type { ResumeUiState } from "./states";

export interface Resume {
  id: string;
  original_filename: string;
  file_kind: "pdf" | "docx";
  size_bytes: number;
  ui_state: ResumeUiState;
  can_retry: boolean;
  /** A plain sentence when ui_state is "failed". */
  error_message: string | null;
  kept_entry_count: number;
  /** Entries the model proposed that were not found in the resume text, so they were left out. */
  dropped_entry_count: number;
  flagged_entry_count: number;
  page_count: number | null;
  run_id: string | null;
  created_at: string;
  parsed_at: string | null;
  confirmed_at: string | null;
}

const BASE = "/api/v1/resume";

/** Limits shown to the user. The server enforces the real ones. */
export const RESUME_MAX_BYTES = 5 * 1024 * 1024;
export const RESUME_EXTENSIONS = [".pdf", ".docx"] as const;

export function fetchResume(signal?: AbortSignal): Promise<Resume | null> {
  return request<Resume | null>("GET", BASE, { signal });
}

export function uploadResume(file: File): Promise<Resume> {
  return uploadFile<Resume>(BASE, file);
}

export function deleteResume(): Promise<void> {
  return request<void>("DELETE", BASE);
}

export function reparseResume(): Promise<Resume> {
  return request<Resume>("POST", `${BASE}/reparse`);
}

export function confirmResume(): Promise<Resume> {
  return request<Resume>("POST", `${BASE}/confirm`);
}

/** A plain link: the browser sends the session cookie and the server checks the owner. */
export const RESUME_DOWNLOAD_URL = `${BASE}/file`;
