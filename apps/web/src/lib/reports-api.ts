import { request } from "./api";

export type ReportFormat = "xlsx" | "csv" | "docx";

export const FORMAT_CHOICES: {
  value: ReportFormat;
  label: string;
  hint: string;
}[] = [
  {
    value: "xlsx",
    label: "Excel workbook (.xlsx)",
    hint: "Sortable sheets: summary, jobs, requirements and evidence.",
  },
  {
    value: "csv",
    label: "CSV (.csv)",
    hint: "One flat table of jobs, for any spreadsheet or tool.",
  },
  {
    value: "docx",
    label: "Word document (.docx)",
    hint: "A report you can read and edit, job by job.",
  },
];

export interface ReportItem {
  id: string;
  format: ReportFormat;
  format_label: string;
  ui_state: "preparing" | "ready" | "failed";
  size_bytes: number | null;
  job_count: number | null;
  criteria: string[];
  query: Record<string, unknown>;
  include_quotes: boolean;
  error_message: string | null;
  created_at: string;
  expires_at: string;
  download_name: string | null;
}

export function fetchReports(signal?: AbortSignal): Promise<ReportItem[]> {
  return request<ReportItem[]>("GET", "/api/v1/reports", { signal });
}

export function createReport(
  format: ReportFormat,
  query: Record<string, unknown>,
  includeQuotes: boolean,
): Promise<ReportItem> {
  return request<ReportItem>("POST", "/api/v1/reports", {
    body: { format, query, include_quotes: includeQuotes },
  });
}

export function deleteReport(id: string): Promise<void> {
  return request<void>("DELETE", `/api/v1/reports/${id}`);
}

export function downloadPath(id: string): string {
  return `/api/v1/reports/${id}/download`;
}

/** "12 Nov", for when a report is deleted. */
export function formatExpiry(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}
