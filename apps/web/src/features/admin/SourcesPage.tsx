import { useState } from "react";
import { fetchSourceLog, fetchSources, pollSource } from "../../lib/admin-api";
import type { AdminSource, FetchLogRow } from "../../lib/admin-api";
import { formatDateTime, formatNumber } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable, Status } from "../../ui";
import type { Tone } from "../../ui";

function stateOf(source: AdminSource): { tone: Tone; label: string } {
  if (!source.enabled) return { tone: "neutral", label: "Switched off" };
  if (
    source.breaker_open_until &&
    new Date(source.breaker_open_until) > new Date()
  )
    return { tone: "danger", label: "Paused after failures" };
  if (source.failure_streak >= 3) return { tone: "warn", label: "Failing" };
  if (source.health_status === "unknown")
    return { tone: "neutral", label: "Not fetched yet" };
  return { tone: "ok", label: "Healthy" };
}

function Log({ rows }: { rows: FetchLogRow[] }) {
  if (rows.length === 0)
    return <p>Nothing has been fetched from this source yet.</p>;
  return (
    <DataTable caption="Recent fetches, newest first">
      <thead>
        <tr>
          <th scope="col">When</th>
          <th scope="col">Result</th>
          <th scope="col" className="num">
            HTTP
          </th>
          <th scope="col" className="num">
            Seen
          </th>
          <th scope="col" className="num">
            New
          </th>
          <th scope="col" className="num">
            Changed
          </th>
          <th scope="col" className="num">
            Closed
          </th>
          <th scope="col" className="num">
            Time
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={index}>
            <td>{formatDateTime(row.started_at)}</td>
            <td>
              {row.outcome.replaceAll("_", " ")}
              {row.error_class ? ` (${row.error_class})` : ""}
            </td>
            <td className="num">{row.http_status ?? "None"}</td>
            <td className="num">{formatNumber(row.jobs_seen)}</td>
            <td className="num">{formatNumber(row.jobs_new)}</td>
            <td className="num">{formatNumber(row.jobs_changed)}</td>
            <td className="num">{formatNumber(row.jobs_closed)}</td>
            <td className="num">{formatNumber(row.duration_ms)} ms</td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

/** Why jobs might not be appearing: each source, when it last worked, and what its fetches did. */
export function SourcesPage() {
  const heading = usePageChrome("Job sources");
  const { data, error, loading, reload } = useAsync(
    (signal) => fetchSources(signal),
    [],
  );
  const [open, setOpen] = useState<string | null>(null);
  const [log, setLog] = useState<FetchLogRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(
    null,
  );

  async function show(key: string) {
    if (open === key) {
      setOpen(null);
      return;
    }
    setOpen(key);
    setLog(null);
    try {
      setLog(await fetchSourceLog(key));
    } catch (caught) {
      setMessage({
        ok: false,
        text:
          caught instanceof Error
            ? caught.message
            : "The log could not be loaded.",
      });
    }
  }

  async function poll(source: AdminSource) {
    setBusy(true);
    setMessage(null);
    try {
      const result = await pollSource(source.key);
      setMessage({ ok: true, text: result.message });
    } catch (caught) {
      setMessage({
        ok: false,
        text:
          caught instanceof Error
            ? caught.message
            : "The source could not be polled.",
      });
    } finally {
      setBusy(false);
      reload();
    }
  }

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        Job sources
      </h1>
      <p className="admin__muted">
        Where jobs come from, when each source last worked and how its recent
        fetches went. A source that keeps failing is paused for a while and
        tries again by itself.
      </p>
      <div role="status">
        {message && (
          <p
            className={
              message.ok
                ? "admin__message"
                : "admin__message admin__message--error"
            }
          >
            {message.text}
          </p>
        )}
      </div>
      {loading && <p>Loading{"…"}</p>}
      {error && (
        <div role="alert" className="admin__message">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}
      {data && (
        <DataTable caption="Job sources">
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col">State</th>
              <th scope="col">Last success</th>
              <th scope="col">Last failure</th>
              <th scope="col" className="num">
                Failures in a row
              </th>
              <th scope="col" className="num">
                Open jobs
              </th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.map((source) => {
              const state = stateOf(source);
              return (
                <tr key={source.key}>
                  <th scope="row">
                    {source.display_name}
                    {!source.enabled && source.enable_blocker ? (
                      <span className="admin__muted">
                        {" "}
                        {source.enable_blocker}
                      </span>
                    ) : null}
                  </th>
                  <td>
                    <Status tone={state.tone} label={state.label} />
                  </td>
                  <td>{formatDateTime(source.last_success_at)}</td>
                  <td>{formatDateTime(source.last_failure_at)}</td>
                  <td className="num">{source.failure_streak}</td>
                  <td className="num">{formatNumber(source.jobs_open)}</td>
                  <td>
                    <div className="console__row">
                      <ActionButton
                        onClick={() => void show(source.key)}
                        aria-expanded={open === source.key}
                      >
                        {open === source.key
                          ? "Hide fetches"
                          : "Recent fetches"}
                        <span className="visually-hidden">
                          {" "}
                          for {source.display_name}
                        </span>
                      </ActionButton>
                      {source.enabled ? (
                        <ActionButton
                          onClick={() => void poll(source)}
                          disabled={busy}
                        >
                          Fetch now
                          <span className="visually-hidden">
                            {" "}
                            from {source.display_name}
                          </span>
                        </ActionButton>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </DataTable>
      )}
      {open && (
        <section aria-label="Recent fetches">
          <h2>
            Recent fetches from{" "}
            {data?.find((s) => s.key === open)?.display_name}
          </h2>
          {log === null ? <p>Loading{"…"}</p> : <Log rows={log} />}
        </section>
      )}
    </>
  );
}
