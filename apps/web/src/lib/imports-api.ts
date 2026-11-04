import { request, uploadFile } from "./api";
import type { PasteResult } from "./jobs-api";

export type ImportKind = "csv" | "xlsx" | "url";
export type ImportState = "queued" | "running" | "done" | "failed";
export type ItemState = "queued" | "created" | "duplicate" | "rejected";

export interface ImportBatch {
  id: string;
  kind: ImportKind;
  /** The file name, or the site name for a web address. */
  label: string;
  default_source: string;
  status: ImportState;
  /** A plain sentence when the whole import failed. */
  error_message: string | null;
  total_rows: number;
  created_count: number;
  duplicate_count: number;
  rejected_count: number;
  /** Columns in the file that were not used. */
  ignored_columns: string[];
  created_at: string;
  finished_at: string | null;
}

export interface ImportItem {
  /** The row number in the file, counting the header as row 1. */
  row_number: number;
  status: ItemState;
  code: string | null;
  message: string | null;
  title: string | null;
  source_url: string | null;
  posting_id: string | null;
}

export interface ImportDetail extends ImportBatch {
  items: ImportItem[];
}

export interface ManualJobInput {
  title: string;
  company: string;
  location: string;
  source_name: string;
  source_url: string | null;
  description: string;
}

/** Limits shown to the user. The server enforces the real ones. */
export const IMPORT_MAX_BYTES = 5 * 1024 * 1024;
export const IMPORT_MAX_ROWS = 200;
export const IMPORT_EXTENSIONS = [".csv", ".xlsx"] as const;

export function enterJob(input: ManualJobInput): Promise<PasteResult> {
  return request<PasteResult>("POST", "/api/v1/jobs/manual", { body: input });
}

export function startUrlImport(url: string, sourceName: string): Promise<ImportBatch> {
  return request<ImportBatch>("POST", "/api/v1/imports/url", {
    body: { url, source_name: sourceName },
  });
}

export function startFileImport(file: File, sourceName: string): Promise<ImportBatch> {
  return uploadFile<ImportBatch>("/api/v1/imports/file", file, undefined, {
    "X-Source-Name": encodeURIComponent(sourceName),
  });
}

export function fetchImports(signal?: AbortSignal): Promise<ImportBatch[]> {
  return request<ImportBatch[]>("GET", "/api/v1/imports", { signal });
}

export function fetchImport(id: string, signal?: AbortSignal): Promise<ImportDetail> {
  return request<ImportDetail>("GET", `/api/v1/imports/${encodeURIComponent(id)}`, { signal });
}

export function isImportBusy(batch: Pick<ImportBatch, "status">): boolean {
  return batch.status === "queued" || batch.status === "running";
}

const KIND_WORDS: Record<ImportKind, string> = {
  csv: "CSV file",
  xlsx: "Excel file",
  url: "Web page",
};

export function kindLabel(kind: ImportKind): string {
  return KIND_WORDS[kind];
}

/** The state said in words. The colour is never the only signal. */
export function describeImport(batch: Pick<ImportBatch, "status" | "created_count" | "rejected_count">): {
  label: string;
  tone: "ok" | "warn" | "danger" | "neutral";
} {
  if (batch.status === "queued") return { label: "Waiting to start", tone: "neutral" };
  if (batch.status === "running") return { label: "Reading", tone: "neutral" };
  if (batch.status === "failed") return { label: "Could not be used", tone: "danger" };
  if (batch.created_count === 0 && batch.rejected_count > 0) return { label: "Nothing added", tone: "danger" };
  if (batch.rejected_count > 0) return { label: "Done, some rows need fixing", tone: "warn" };
  return { label: "Done", tone: "ok" };
}

const ITEM_WORDS: Record<ItemState, { label: string; tone: "ok" | "warn" | "danger" | "neutral" }> = {
  queued: { label: "Waiting", tone: "neutral" },
  created: { label: "Added", tone: "ok" },
  duplicate: { label: "Already saved", tone: "neutral" },
  rejected: { label: "Not added", tone: "danger" },
};

export function describeItem(status: ItemState) {
  return ITEM_WORDS[status];
}
