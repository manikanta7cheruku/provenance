// A small stateful fake of the reports API, so the export panel is exercised in every state:
// being made, ready, failed and retried, refused, and deleted.

export interface FakeReport {
  id: string;
  format: "xlsx" | "csv" | "docx";
  state: "preparing" | "ready" | "failed";
  reads: number;
  query: Record<string, unknown>;
  quotes: boolean;
  created: string;
}

export interface FakeReports {
  items: FakeReport[];
  /** What the next report turns into once it has been read twice: ready, failed, or never finishes. */
  outcome: "ready" | "failed" | "stay";
  /** Make the next request be refused with this message (409). */
  refuse: string | null;
  calls: string[];
  seq: number;
}

export const newReports = (over: Partial<FakeReports> = {}): FakeReports => ({
  items: [],
  outcome: "ready",
  refuse: null,
  calls: [],
  seq: 0,
  ...over,
});

const LABELS = {
  xlsx: "Excel workbook",
  csv: "CSV",
  docx: "Word document",
} as const;

function criteria(query: Record<string, unknown>): string[] {
  const view = String(query.view ?? "active");
  const lines = [`List: ${view.charAt(0).toUpperCase()}${view.slice(1)}`];
  if (typeof query.text === "string" && query.text)
    lines.push(`Words: ${query.text}`);
  if (typeof query.company === "string" && query.company)
    lines.push(`Company: ${query.company}`);
  return lines;
}

function out(r: FakeReport) {
  const ready = r.state === "ready";
  return {
    id: r.id,
    format: r.format,
    format_label: LABELS[r.format],
    ui_state: r.state,
    size_bytes: ready ? 18432 : null,
    job_count: ready ? 4 : null,
    criteria: criteria(r.query),
    query: r.query,
    include_quotes: r.quotes,
    error_message:
      r.state === "failed"
        ? "The report could not be made. Your jobs are safe. Try again."
        : null,
    created_at: r.created,
    expires_at: "2026-11-12T09:00:00Z",
    download_name: ready
      ? `Provenance opportunities 2026-11-05.${r.format}`
      : null,
  };
}

export function handleReports(
  path: string,
  method: string,
  body: unknown,
  fake: { reports: FakeReports },
): { status: number; json?: unknown } | null {
  const m = path.match(/^\/api\/v1\/reports(?:\/([^/]+)(\/download)?)?$/);
  if (!m) return null;
  const s = fake.reports;
  if (!m[1]) {
    if (method === "GET") {
      for (const r of s.items) {
        if (r.state === "preparing") {
          r.reads += 1;
          if (r.reads >= 2 && s.outcome !== "stay") r.state = s.outcome;
        }
      }
      return { status: 200, json: s.items.map(out).reverse() };
    }
    if (method === "POST") {
      const b = (body ?? {}) as {
        format?: FakeReport["format"];
        query?: Record<string, unknown>;
        include_quotes?: boolean;
      };
      s.calls.push(
        `create:${b.format}:${JSON.stringify(b.query ?? {})}:${b.include_quotes ? "quotes" : "plain"}`,
      );
      if (s.refuse)
        return {
          status: 409,
          json: { code: "REPORT_IN_PROGRESS", message: s.refuse },
        };
      s.seq += 1;
      const item: FakeReport = {
        id: `rep-${s.seq}`,
        format: b.format ?? "xlsx",
        state: "preparing",
        reads: 0,
        query: b.query ?? {},
        quotes: Boolean(b.include_quotes),
        created: "2026-11-05T09:30:00Z",
      };
      s.items.push(item);
      return { status: 202, json: out(item) };
    }
  }
  const item = s.items.find((r) => r.id === m[1]);
  if (!item)
    return { status: 404, json: { code: "NOT_FOUND", message: "Not found." } };
  if (method === "DELETE") {
    s.calls.push(`delete:${item.id}`);
    s.items = s.items.filter((r) => r.id !== item.id);
    return { status: 204 };
  }
  if (method === "GET" && !m[2]) return { status: 200, json: out(item) };
  return null;
}
