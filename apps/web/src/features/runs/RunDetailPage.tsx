import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { fetchRun } from "../../lib/runs-api";
import { describeState, isActiveState } from "../../lib/states";
import { formatCost, formatDateTime, formatDuration, formatNumber } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable, Status } from "../../ui";
import "./runs.css";

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const { data, error, loading, reload } = useAsync((signal) => fetchRun(runId, signal), [runId]);
  const title = data ? data.run.workflow_label : "Run";
  const heading = usePageChrome(title);

  const active = data ? isActiveState(data.run.ui_state) : false;
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(reload, 3000);
    return () => window.clearInterval(timer);
  }, [active, reload]);

  if (error instanceof ApiError && error.status === 404) {
    return (
      <div className="runs">
        <h1 ref={heading} tabIndex={-1}>
          Run not found
        </h1>
        <p>This run does not exist, or it is not yours.</p>
        <Link to="/runs">Back to runs</Link>
      </div>
    );
  }

  return (
    <div className="runs">
      <p>
        <Link to="/runs">Back to runs</Link>
      </p>
      <h1 ref={heading} tabIndex={-1}>
        {title}
      </h1>

      {loading && <p>Loading run{"\u2026"}</p>}
      {error && (
        <div role="alert" className="runs__error">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}

      {data && (
        <>
          <p role="status">
            <Status tone={describeState(data.run.ui_state).tone} label={describeState(data.run.ui_state).label} />
            <br />
            {describeState(data.run.ui_state).explanation}
          </p>
          <p>
            Started {formatDateTime(data.run.started_at ?? data.run.created_at)}. Duration:{" "}
            {formatDuration(data.run.duration_ms)}.
          </p>
          {data.error_summary && (
            <div className="runs__error">
              <strong>What went wrong</strong>
              <p>{data.error_summary}</p>
            </div>
          )}

          <h2>Steps</h2>
          {data.steps.length === 0 ? (
            <p>No steps recorded yet.</p>
          ) : (
            <ol className="runs__steps">
              {data.steps.map((step) => {
                const info = describeState(step.ui_state);
                return (
                  <li key={step.ordinal}>
                    <span className="runs__step-name">{step.step_name}</span>
                    <Status tone={info.tone} label={info.label} />
                    <span>{formatDuration(step.duration_ms)}</span>
                  </li>
                );
              })}
            </ol>
          )}

          <h2>Model usage</h2>
          {data.llm_calls.length === 0 ? (
            <p>No model calls were made in this run.</p>
          ) : (
            <DataTable caption="Model calls (metadata only, no text is stored)">
              <thead>
                <tr>
                  <th scope="col">Purpose</th>
                  <th scope="col">Model</th>
                  <th scope="col">Prompt version</th>
                  <th scope="col" className="num">Input tokens</th>
                  <th scope="col" className="num">Output tokens</th>
                  <th scope="col">Estimated cost</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.llm_calls.map((call, index) => (
                  <tr key={index}>
                    <td>{call.purpose}</td>
                    <td>
                      {call.provider} / {call.model}
                    </td>
                    <td>{call.prompt_version ?? "None"}</td>
                    <td className="num">{formatNumber(call.input_tokens)}</td>
                    <td className="num">{formatNumber(call.output_tokens)}</td>
                    <td>{formatCost(call.estimated_cost_usd)}</td>
                    <td>{call.status === "ok" ? "Succeeded" : "Failed"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </>
      )}
    </div>
  );
}
