import { useEffect } from "react";
import { Link } from "react-router-dom";
import { fetchHealth } from "../../lib/admin-api";
import type { Health, Level } from "../../lib/admin-api";
import { formatDateTime, formatNumber, formatSeconds } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable, Status } from "../../ui";
import type { Tone } from "../../ui";

const REFRESH_MS = 15000;

const TONE: Record<Level, Tone> = {
  ok: "ok",
  warning: "warn",
  critical: "danger",
  unknown: "neutral",
};
const LABEL: Record<Level, string> = {
  ok: "Healthy",
  warning: "Needs a look",
  critical: "Critical",
  unknown: "Not measured",
};

function Requests({ data }: { data: Health["requests"] }) {
  if (!data.measured) {
    return (
      <p>
        Not measured yet. This API process has not answered a request in the
        last {data.window_minutes} minutes.
      </p>
    );
  }
  return (
    <p>
      In the last {data.window_minutes} minutes this API process answered{" "}
      {formatNumber(data.requests)} requests: {formatNumber(data.server_errors)}{" "}
      failed on our side and {formatNumber(data.client_errors)} were refused as
      bad requests. Half took {data.p50_ms} ms or less, and the slowest 5
      percent took {data.p95_ms} ms or more.
    </p>
  );
}

/** Is the system healthy, and is anything stuck. Every line answers one question an operator asks. */
export function HealthPage() {
  const heading = usePageChrome("Health");
  const { data, error, loading, refreshing, reload } = useAsync(
    (signal) => fetchHealth(signal),
    [],
  );

  useEffect(() => {
    const timer = window.setInterval(reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [reload]);

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        Health
      </h1>
      <p className="admin__muted">
        Counters and operational records only. Administrators never see resumes,
        profile entries, evidence or jobs.
      </p>
      <ActionButton onClick={reload} disabled={refreshing}>
        {refreshing ? "Refreshing…" : "Refresh"}
      </ActionButton>

      {loading && <p>Loading{"…"}</p>}
      {error && (
        <div role="alert" className="admin__message">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}

      {data && (
        <>
          <p role="status" className="console__headline">
            <Status tone={TONE[data.status]} label={LABEL[data.status]} />{" "}
            <span>{data.headline}</span>
          </p>
          <p className="admin__muted">
            Version {data.version}, {data.environment}. Measured{" "}
            {formatDateTime(data.generated_at)}.
          </p>

          <h2>What needs attention</h2>
          {data.alerts.length === 0 ? (
            <p>Nothing. Every rule is quiet.</p>
          ) : (
            <ul className="console__alerts" aria-label="Alerts">
              {data.alerts.map((alert) => (
                <li
                  key={alert.key}
                  className={`console__alert console__alert--${alert.severity}`}
                >
                  <div className="console__alerthead">
                    <Status
                      tone={alert.severity === "critical" ? "danger" : "warn"}
                      label={
                        alert.severity === "critical" ? "Critical" : "Warning"
                      }
                    />
                    <strong>{alert.title}</strong>
                  </div>
                  <p>{alert.detail}</p>
                  <p>
                    <strong>Do first:</strong> {alert.action}
                  </p>
                  <p className="admin__muted">Runbook: {alert.runbook}</p>
                </li>
              ))}
            </ul>
          )}

          <h2>Parts of the system</h2>
          <DataTable caption="Each part and how it is doing">
            <thead>
              <tr>
                <th scope="col">Part</th>
                <th scope="col">State</th>
                <th scope="col">Detail</th>
              </tr>
            </thead>
            <tbody>
              {data.components.map((part) => (
                <tr key={part.name}>
                  <th scope="row">{part.name}</th>
                  <td>
                    <Status
                      tone={TONE[part.status]}
                      label={LABEL[part.status]}
                    />
                  </td>
                  <td>{part.detail}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>

          <h2>Requests</h2>
          <Requests data={data.requests} />
          <p className="admin__muted">
            Kept in this API process only, so it describes the process that
            answered. A shared measurement across processes comes with
            deployment.
          </p>

          <h2>Work that is retrying or stuck</h2>
          {data.trouble_tasks.length === 0 ? (
            <p>
              None. Nothing is being retried and nothing has outlived its lease.
            </p>
          ) : (
            <DataTable caption="Tasks to look at first">
              <thead>
                <tr>
                  <th scope="col">Task</th>
                  <th scope="col">State</th>
                  <th scope="col" className="num">
                    Tries
                  </th>
                  <th scope="col">Last error</th>
                  <th scope="col">Run</th>
                </tr>
              </thead>
              <tbody>
                {data.trouble_tasks.map((task) => (
                  <tr key={task.id}>
                    <td>{task.task_type}</td>
                    <td>
                      <Status
                        tone={task.state === "stuck" ? "danger" : "warn"}
                        label={task.state === "stuck" ? "Stuck" : "Retrying"}
                      />
                    </td>
                    <td className="num">
                      {task.attempts} of {task.max_attempts}
                    </td>
                    <td>{task.last_error ?? "None"}</td>
                    <td>
                      {task.run_id ? (
                        <Link to={`/admin/runs?run=${task.run_id}`}>
                          Trace this run
                        </Link>
                      ) : (
                        "No run"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
          <p>
            Waiting now:{" "}
            {formatNumber(
              (data.queue_by_state.queued ?? 0) +
                (data.queue_by_state.retry_scheduled ?? 0),
            )}
            . Oldest: {formatSeconds(data.oldest_waiting_seconds)}.{" "}
            <Link to="/admin/queue">
              Open the queue, workers and dead letters
            </Link>
            .
          </p>

          <h2>Why jobs might not be appearing</h2>
          {data.sources.filter((s) => s.enabled).length === 0 ? (
            <p>
              No job source is switched on, so nothing is fetched.{" "}
              <Link to="/admin/sources">Open sources</Link>.
            </p>
          ) : (
            <DataTable caption="Switched-on job sources">
              <thead>
                <tr>
                  <th scope="col">Source</th>
                  <th scope="col">State</th>
                  <th scope="col">Last success</th>
                  <th scope="col" className="num">
                    Failures in a row
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.sources
                  .filter((s) => s.enabled)
                  .map((source) => (
                    <tr key={source.key}>
                      <th scope="row">{source.name}</th>
                      <td>
                        <Status
                          tone={
                            source.breaker_open
                              ? "danger"
                              : source.failure_streak >=
                                  data.thresholds.source_failure_streak
                                ? "warn"
                                : "ok"
                          }
                          label={
                            source.breaker_open
                              ? "Paused after failures"
                              : source.failure_streak >=
                                  data.thresholds.source_failure_streak
                                ? "Failing"
                                : "Healthy"
                          }
                        />
                      </td>
                      <td>{formatDateTime(source.last_success_at)}</td>
                      <td className="num">{source.failure_streak}</td>
                    </tr>
                  ))}
              </tbody>
            </DataTable>
          )}

          <h2>Abuse and security, last 24 hours</h2>
          {data.security_24h.length === 0 &&
          data.rate_limits_24h.length === 0 ? (
            <p>No security events and no rate limit was exceeded.</p>
          ) : (
            <>
              {data.security_24h.length > 0 && (
                <DataTable caption="Security events">
                  <thead>
                    <tr>
                      <th scope="col">Event</th>
                      <th scope="col" className="num">
                        Count
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.security_24h.map((event) => (
                      <tr key={event.action}>
                        <td>{event.label}</td>
                        <td className="num">{formatNumber(event.count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
              {data.rate_limits_24h.length > 0 && (
                <DataTable caption="Rate limits exceeded (counters over their limit, nobody is named)">
                  <thead>
                    <tr>
                      <th scope="col">Limit</th>
                      <th scope="col" className="num">
                        Counters over
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rate_limits_24h.map((row) => (
                      <tr key={row.policy}>
                        <td>{row.policy.replaceAll("_", " ")}</td>
                        <td className="num">
                          {formatNumber(row.counters_over)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </>
          )}

          <details className="console__how">
            <summary>How these alerts are decided</summary>
            <p>
              These limits are starting points chosen before there was traffic
              to measure. They will be set from what the system really does, and
              each alert has a runbook section.
            </p>
            <ul>
              <li>
                Work waiting longer than{" "}
                {formatSeconds(data.thresholds.queue_stale_warning_seconds)} is
                a warning, and longer than{" "}
                {formatSeconds(data.thresholds.queue_stale_critical_seconds)} is
                critical.
              </li>
              <li>
                A source that fails {data.thresholds.source_failure_streak}{" "}
                times in a row is flagged.
              </li>
              <li>
                {Math.round(data.thresholds.llm_error_rate * 100)} percent of
                model calls failing is flagged.
              </li>
              <li>
                {Math.round(data.thresholds.server_error_rate * 100)} percent of
                requests failing on our side is critical, and a slowest 5
                percent of {data.thresholds.p95_ms} ms or more is a warning.
              </li>
              <li>
                {data.thresholds.auth_failures_per_hour} failed sign-ins in an
                hour is flagged.
              </li>
              <li>
                {data.thresholds.daily_spend_ceiling_usd > 0
                  ? `Model spend is flagged at 80 percent of $${data.thresholds.daily_spend_ceiling_usd.toFixed(2)} a day.`
                  : "No daily spend ceiling is set, so spend raises no alert."}
              </li>
            </ul>
          </details>
        </>
      )}
    </>
  );
}
