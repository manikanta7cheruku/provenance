import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchRuns } from "../../lib/runs-api";
import { describeState, isActiveState } from "../../lib/states";
import { formatDateTime, formatDuration } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable, Status } from "../../ui";
import "./runs.css";

const REFRESH_MS = 4000;

export function RunsPage() {
  const heading = usePageChrome("Runs");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useAsync((signal) => fetchRuns(offset, signal), [offset]);

  const activeCount = data?.items.filter((run) => isActiveState(run.ui_state)).length ?? 0;

  // While something is running, keep the list fresh. Stops by itself when everything finished.
  useEffect(() => {
    if (activeCount === 0) return;
    const timer = window.setInterval(reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [activeCount, reload]);

  return (
    <div className="runs">
      <h1 ref={heading} tabIndex={-1}>
        Runs
      </h1>
      <p className="runs__lead">
        A history of what the system did for you: parsing your resume and analyzing jobs. It shows
        steps, timing and model usage, never the text of your documents.
      </p>

      <p role="status" className="visually-hidden">
        {data ? (activeCount > 0 ? `${activeCount} runs in progress.` : "No runs in progress.") : ""}
      </p>

      {loading && <p>Loading runs{"\u2026"}</p>}

      {error && (
        <div role="alert" className="runs__error">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}

      {data && data.items.length === 0 && (
        <p>
          No runs yet. A run appears here when you upload a resume or analyze a job. Nothing is
          wrong: those features arrive in the next checkpoints.
        </p>
      )}

      {data && data.items.length > 0 && (
        <>
          <DataTable caption={`Your runs (${data.total})`}>
            <thead>
              <tr>
                <th scope="col">Workflow</th>
                <th scope="col">State</th>
                <th scope="col">Started</th>
                <th scope="col">Duration</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((run) => {
                const info = describeState(run.ui_state);
                return (
                  <tr key={run.id}>
                    <td>
                      <Link to={`/runs/${run.id}`}>{run.workflow_label}</Link>
                    </td>
                    <td>
                      <Status tone={info.tone} label={info.label} />
                    </td>
                    <td>{formatDateTime(run.started_at ?? run.created_at)}</td>
                    <td>{formatDuration(run.duration_ms)}</td>
                  </tr>
                );
              })}
            </tbody>
          </DataTable>
          <div className="runs__pager">
            <ActionButton disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - data.limit))}>
              Newer
            </ActionButton>
            <span>
              {offset + 1} to {Math.min(offset + data.limit, data.total)} of {data.total}
            </span>
            <ActionButton disabled={offset + data.limit >= data.total} onClick={() => setOffset(offset + data.limit)}>
              Older
            </ActionButton>
          </div>
        </>
      )}
    </div>
  );
}
