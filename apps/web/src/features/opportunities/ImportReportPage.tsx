import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { describeImport, describeItem, fetchImport, isImportBusy, kindLabel } from "../../lib/imports-api";
import type { ImportDetail } from "../../lib/imports-api";
import { formatDateTime } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { ActionButton, DataTable, EmptyState, Notice, PageHeader, Section, Skeleton, Status } from "../../ui";
import "./opportunities.css";

const REFRESH_MS = 2000;

function Counts({ batch }: { batch: ImportDetail }) {
  return (
    <dl className="import__counts">
      <div>
        <dt>Added</dt>
        <dd>{batch.created_count}</dd>
      </div>
      <div>
        <dt>Already saved</dt>
        <dd>{batch.duplicate_count}</dd>
      </div>
      <div>
        <dt>Not added</dt>
        <dd>{batch.rejected_count}</dd>
      </div>
    </dl>
  );
}

function Report({ batch }: { batch: ImportDetail }) {
  const state = describeImport(batch);
  const busy = isImportBusy(batch);
  return (
    <>
      <div className="job__state">
        <Status tone={state.tone} label={state.label} />
        <span className="job__explanation">
          {kindLabel(batch.kind)}: {batch.label}. Started {formatDateTime(batch.created_at)}.
        </span>
      </div>

      {batch.status === "failed" ? (
        <Notice tone="danger" title="This import could not be used">
          <p>{batch.error_message}</p>
          <p>Nothing was added. Fix the file and import it again.</p>
        </Notice>
      ) : null}

      {busy ? (
        <Notice tone="info" title="Reading your import">
          <p>You can leave this page. It keeps going and shows here when it is done.</p>
        </Notice>
      ) : null}

      {batch.status === "done" ? <Counts batch={batch} /> : null}

      {batch.ignored_columns.length > 0 ? (
        <p className="job__note">Columns that were not used: {batch.ignored_columns.join(", ")}.</p>
      ) : null}

      {batch.items.length > 0 ? (
        <DataTable caption={`Import report, ${batch.items.length} ${batch.items.length === 1 ? "row" : "rows"}`}>
          <thead>
            <tr>
              <th scope="col" className="num">
                Row
              </th>
              <th scope="col">Job</th>
              <th scope="col">Result</th>
              <th scope="col">What happened</th>
            </tr>
          </thead>
          <tbody>
            {batch.items.map((item) => {
              const info = describeItem(item.status);
              return (
                <tr key={item.row_number}>
                  <td className="num">{item.row_number}</td>
                  <th scope="row">
                    {item.posting_id ? (
                      <Link to={`/opportunities/${item.posting_id}`} className="jobs__link">
                        {item.title ?? "Untitled posting"}
                      </Link>
                    ) : (
                      <span>{item.title ?? "Untitled row"}</span>
                    )}
                    {item.source_url ? <span className="row-sub">{item.source_url}</span> : null}
                  </th>
                  <td>
                    <Status tone={info.tone} label={info.label} />
                  </td>
                  <td>{item.message ?? (item.status === "created" ? "Saved and being read." : "")}</td>
                </tr>
              );
            })}
          </tbody>
        </DataTable>
      ) : batch.status === "done" ? (
        <EmptyState
          title="No rows to show"
          why="The file had a header but no jobs we could read under it."
          next="Check the file and import it again."
        />
      ) : null}
    </>
  );
}

export function ImportReportPage() {
  useDocumentTitle("Import report");
  const { batchId = "" } = useParams();
  const report = useAsync((signal) => fetchImport(batchId, signal), [batchId]);
  const busy = report.data ? isImportBusy(report.data) : false;

  // While the import is being read, keep asking. It stops by itself when the import ends.
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(report.reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [busy, report.reload]);

  return (
    <>
      <PageHeader
        title="Import report"
        description="What happened to each row or page you brought in. Nothing is shared with anyone else."
      />
      <p className="job__back">
        <Link to="/opportunities">Back to your jobs</Link>
      </p>
      <Section title="Result">
        {report.error ? (
          <Notice tone="danger" title="This report could not be loaded">
            <p>{report.error.message} Nothing was changed.</p>
            <p>
              <ActionButton onClick={report.reload}>Try again</ActionButton>
            </p>
          </Notice>
        ) : !report.data ? (
          <Skeleton label="Loading the report" lines={4} />
        ) : (
          <Report batch={report.data} />
        )}
      </Section>
    </>
  );
}
