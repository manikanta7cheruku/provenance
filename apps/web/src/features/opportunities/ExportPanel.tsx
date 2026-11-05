import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import {
  createReport,
  deleteReport,
  downloadPath,
  fetchReports,
  FORMAT_CHOICES,
  formatExpiry,
} from "../../lib/reports-api";
import type { ReportFormat, ReportItem } from "../../lib/reports-api";
import { useAsync } from "../../lib/useAsync";
import { queryToStored } from "../../lib/workbench-api";
import type { Query } from "../../lib/workbench-api";
import {
  ActionButton,
  Checkbox,
  formatBytes,
  Notice,
  Select,
  Status,
} from "../../ui";

const REFRESH_MS = 2000;

function ReportRow({
  item,
  onRetry,
  onDelete,
  busy,
}: {
  item: ReportItem;
  onRetry: (item: ReportItem) => void;
  onDelete: (item: ReportItem) => void;
  busy: boolean;
}) {
  const where = item.criteria.join(". ");
  return (
    <li className="export__item">
      <div className="export__head">
        <strong>{item.format_label}</strong>
        {item.ui_state === "preparing" ? (
          <Status tone="neutral" label="Being made" />
        ) : null}
        {item.ui_state === "ready" ? <Status tone="ok" label="Ready" /> : null}
        {item.ui_state === "failed" ? (
          <Status tone="danger" label="Could not be made" />
        ) : null}
      </div>
      <p className="field__hint">
        {item.ui_state === "ready" && item.job_count !== null
          ? `${item.job_count} ${item.job_count === 1 ? "job" : "jobs"}, ${formatBytes(item.size_bytes ?? 0)}. `
          : ""}
        Asked for {formatDateTime(item.created_at)}.
        {item.ui_state === "ready"
          ? ` Deleted on ${formatExpiry(item.expires_at)}.`
          : ""}
      </p>
      <p className="field__hint">
        {where}
        {item.include_quotes ? ". With evidence quotes" : ""}
      </p>
      {item.error_message ? <p role="alert">{item.error_message}</p> : null}
      <div className="export__actions">
        {item.ui_state === "ready" ? (
          <a
            className="button button--primary"
            href={downloadPath(item.id)}
            download={item.download_name ?? undefined}
          >
            Download{" "}
            <span className="visually-hidden">
              {item.format_label} made {formatDateTime(item.created_at)}
            </span>
          </a>
        ) : null}
        {item.ui_state === "failed" ? (
          <ActionButton onClick={() => onRetry(item)} disabled={busy}>
            Try again
          </ActionButton>
        ) : null}
        <ActionButton
          variant="quiet"
          onClick={() => onDelete(item)}
          disabled={busy}
        >
          Delete
          <span className="visually-hidden">
            {" "}
            {item.format_label} made {formatDateTime(item.created_at)}
          </span>
        </ActionButton>
      </div>
    </li>
  );
}

/** Make a report of the jobs in the list you are looking at, and download it when it is ready. */
export function ExportPanel({ query, count }: { query: Query; count: number }) {
  const reports = useAsync((signal) => fetchReports(signal), []);
  const [format, setFormat] = useState<ReportFormat>("xlsx");
  const [quotes, setQuotes] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");

  const list = reports.data ?? [];
  const waiting = list.some((r) => r.ui_state === "preparing");
  const { reload } = reports;
  useEffect(() => {
    if (!waiting) return;
    const timer = window.setInterval(reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [waiting, reload]);

  async function make(
    fmt: ReportFormat,
    stored: Record<string, unknown>,
    withQuotes: boolean,
  ) {
    setBusy(true);
    setError(null);
    try {
      await createReport(fmt, stored, withQuotes);
      setAnnounce("Your report is being made.");
      reload();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The report could not be started. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: ReportItem) {
    setBusy(true);
    setError(null);
    try {
      await deleteReport(item.id);
      setAnnounce("The report was deleted.");
      reload();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The report could not be deleted.",
      );
    } finally {
      setBusy(false);
    }
  }

  const choice = FORMAT_CHOICES.find((c) => c.value === format);
  return (
    <details className="export">
      <summary>Export these jobs</summary>
      <div className="export__body">
        <p>
          Makes a report of the {count} {count === 1 ? "job" : "jobs"} in this
          list, with the filters now applied. It is made from what is stored
          here, says when it was made, and is never sent anywhere. Exporting is
          free and is not counted against your plan.
        </p>
        <div className="export__form">
          <Select
            label="Format"
            value={format}
            hint={choice?.hint}
            onChange={(event) => setFormat(event.target.value as ReportFormat)}
          >
            {FORMAT_CHOICES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </Select>
          {format !== "csv" ? (
            <Checkbox
              label="Include short evidence quotes"
              hint="Off by default. A quote is a line from your own profile, so keep the file private if you add it."
              checked={quotes}
              onChange={(event) => setQuotes(event.target.checked)}
            />
          ) : null}
          <ActionButton
            variant="primary"
            disabled={busy || count === 0}
            onClick={() =>
              void make(
                format,
                queryToStored(query),
                format !== "csv" && quotes,
              )
            }
          >
            Make report
          </ActionButton>
        </div>
        {count === 0 ? (
          <p className="field__hint">
            There are no jobs in this list to export.
          </p>
        ) : null}
        {error ? (
          <Notice tone="danger" title="That did not work">
            <p>{error}</p>
          </Notice>
        ) : null}
        <p className="visually-hidden" role="status">
          {announce}
        </p>
        {reports.error ? (
          <Notice tone="warn">
            <p>
              Your earlier reports could not be loaded. You can still make a new
              one.
            </p>
          </Notice>
        ) : null}
        {list.length > 0 ? (
          <>
            <h3 className="export__title">Your reports</h3>
            <p className="field__hint">
              Reports are deleted after a few days. Keep a copy if you want one.
            </p>
            <ul className="export__list" aria-label="Your reports">
              {list.map((item) => (
                <ReportRow
                  key={item.id}
                  item={item}
                  busy={busy}
                  onRetry={(r) =>
                    void make(r.format, r.query, r.include_quotes)
                  }
                  onDelete={(r) => void remove(r)}
                />
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </details>
  );
}
