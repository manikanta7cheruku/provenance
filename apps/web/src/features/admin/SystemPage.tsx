import { useEffect, useState } from "react";
import { fetchOverview, fetchSystem, requeueTask } from "../../lib/admin-api";
import type { DeadLetter } from "../../lib/admin-api";
import { formatCost, formatDateTime, formatNumber, formatSeconds } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, ConfirmDialog, DataTable, Status } from "../../ui";

const REFRESH_MS = 15000;
const STATE_ORDER = ["queued", "running", "retry_scheduled", "dead_letter", "succeeded", "cancelled"];

export function SystemPage() {
  const heading = usePageChrome("System");
  const { data, error, loading, refreshing, reload } = useAsync(
    async (signal) => {
      const [system, overview] = await Promise.all([fetchSystem(signal), fetchOverview(signal)]);
      return { system, overview };
    },
    [],
  );
  const [pending, setPending] = useState<DeadLetter | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const timer = window.setInterval(reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [reload]);

  async function confirmRequeue() {
    if (!pending) return;
    setBusy(true);
    try {
      const result = await requeueTask(pending.id);
      setMessage({ ok: true, text: result.message });
    } catch (caught) {
      setMessage({ ok: false, text: caught instanceof Error ? caught.message : "Something went wrong." });
    } finally {
      setBusy(false);
      setPending(null);
      reload();
    }
  }

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        System
      </h1>
      <p className="admin__muted">
        Counters and queue state only. Administrators never see resumes, profile entries,
        evidence or jobs.
      </p>
      <ActionButton onClick={reload} disabled={refreshing}>
        {refreshing ? "Refreshing\u2026" : "Refresh"}
      </ActionButton>

      <div role="status">
        {message && <p className={message.ok ? "admin__message" : "admin__message admin__message--error"}>{message.text}</p>}
      </div>
      {loading && <p>Loading{"\u2026"}</p>}
      {error && (
        <div role="alert" className="admin__message">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}

      {data && (
        <>
          <dl className="admin__counts">
            <div>
              <dt>Users</dt>
              <dd>{formatNumber(data.overview.users)}</dd>
            </div>
            <div>
              <dt>Email confirmed</dt>
              <dd>{formatNumber(data.overview.verified_users)}</dd>
            </div>
            <div>
              <dt>Active sessions</dt>
              <dd>{formatNumber(data.overview.active_sessions)}</dd>
            </div>
            <div>
              <dt>Oldest waiting task</dt>
              <dd>{formatSeconds(data.system.queue.oldest_waiting_seconds)}</dd>
            </div>
          </dl>

          <DataTable caption="Queue by state">
            <thead>
              <tr>
                <th scope="col">State</th>
                <th scope="col" className="num">Tasks</th>
              </tr>
            </thead>
            <tbody>
              {STATE_ORDER.map((state) => (
                <tr key={state}>
                  <td>{state.replace("_", " ")}</td>
                  <td className="num">{formatNumber(data.system.queue.by_state[state] ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>

          {data.system.workers.length === 0 ? (
            <p role="alert" className="admin__message">
              No worker has reported in. Queued work, including email, will not be processed. See
              the runbook "Worker failure".
            </p>
          ) : (
            <DataTable caption="Workers">
              <thead>
                <tr>
                  <th scope="col">Worker</th>
                  <th scope="col">Status</th>
                  <th scope="col">Last heartbeat</th>
                  <th scope="col" className="num">Tasks handled</th>
                </tr>
              </thead>
              <tbody>
                {data.system.workers.map((worker) => (
                  <tr key={worker.worker_id}>
                    <td>{worker.worker_id}</td>
                    <td>
                      <Status
                        tone={worker.status === "alive" ? "ok" : "danger"}
                        label={worker.status === "alive" ? "Alive" : "Stale"}
                      />
                    </td>
                    <td>{formatDateTime(worker.last_seen_at)}</td>
                    <td className="num">{formatNumber(worker.tasks_processed)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}

          {data.system.dead_letters.length === 0 ? (
            <p>No dead-lettered tasks.</p>
          ) : (
            <DataTable caption={`Dead letters (${data.system.dead_letters.length})`}>
              <thead>
                <tr>
                  <th scope="col">Task</th>
                  <th scope="col" className="num">Attempts</th>
                  <th scope="col">Last error</th>
                  <th scope="col">Failed</th>
                  <th scope="col">Action</th>
                </tr>
              </thead>
              <tbody>
                {data.system.dead_letters.map((task) => (
                  <tr key={task.id}>
                    <td>{task.task_type}</td>
                    <td className="num">
                      {task.attempts} of {task.max_attempts}
                    </td>
                    <td>{task.last_error ?? "None"}</td>
                    <td>{formatDateTime(task.finished_at)}</td>
                    <td>
                      {task.requeueable ? (
                        <ActionButton onClick={() => setPending(task)}>Requeue</ActionButton>
                      ) : (
                        <span>Cannot requeue: one-time link erased</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}

          <h2>AI usage, last 24 hours</h2>
          <p>
            {formatNumber(data.system.ai_usage_24h.calls)} calls,{" "}
            {formatNumber(data.system.ai_usage_24h.errors)} failed.{" "}
            {formatNumber(data.system.ai_usage_24h.input_tokens)} input and{" "}
            {formatNumber(data.system.ai_usage_24h.output_tokens)} output tokens. Estimated cost:{" "}
            {formatCost(data.system.ai_usage_24h.estimated_cost_usd)}.
          </p>
          {data.system.ai_usage_24h.by_model.length > 0 && (
            <DataTable caption="By model">
              <thead>
                <tr>
                  <th scope="col">Model</th>
                  <th scope="col" className="num">Calls</th>
                  <th scope="col" className="num">Input tokens</th>
                  <th scope="col" className="num">Output tokens</th>
                  <th scope="col">Estimated cost</th>
                </tr>
              </thead>
              <tbody>
                {data.system.ai_usage_24h.by_model.map((row) => (
                  <tr key={`${row.provider}/${row.model}`}>
                    <td>
                      {row.provider} / {row.model}
                    </td>
                    <td className="num">{formatNumber(row.calls)}</td>
                    <td className="num">{formatNumber(row.input_tokens)}</td>
                    <td className="num">{formatNumber(row.output_tokens)}</td>
                    <td>{formatCost(row.estimated_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </>
      )}

      <ConfirmDialog
        open={pending !== null}
        title="Requeue this task?"
        confirmLabel="Requeue"
        busy={busy}
        onConfirm={() => void confirmRequeue()}
        onCancel={() => setPending(null)}
      >
        <p>
          The task <strong>{pending?.task_type}</strong> gets a fresh set of attempts. If the cause
          of the failure is still there, it will fail again.
        </p>
      </ConfirmDialog>
    </>
  );
}
