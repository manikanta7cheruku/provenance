import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchTrace } from "../../lib/admin-api";
import type { Trace } from "../../lib/admin-api";
import { formatCost, formatDateTime, formatNumber } from "../../lib/format";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable, TextField } from "../../ui";

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Find a run by the reference a person quotes. It shows the queue's tasks and the model calls for that run and
 * nothing the person wrote: steps, what the run was about and any text belong to the person.
 */
export function TracePage() {
  const heading = usePageChrome("Find a run");
  const [params, setParams] = useSearchParams();
  const asked = params.get("run") ?? "";
  const [text, setText] = useState(asked);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!asked) {
      setTrace(null);
      setError(null);
      return;
    }
    if (!ID.test(asked.trim())) {
      setTrace(null);
      setError(
        "That is not a run reference. It looks like 3f2a1c90-1b2c-4d5e-8f60-123456789abc.",
      );
      return;
    }
    let live = true;
    setBusy(true);
    setError(null);
    fetchTrace(asked.trim())
      .then((result) => live && setTrace(result))
      .catch(
        (caught) =>
          live &&
          setError(
            caught instanceof Error
              ? caught.message
              : "The run could not be traced.",
          ),
      )
      .finally(() => live && setBusy(false));
    return () => {
      live = false;
    };
  }, [asked]);

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        Find a run
      </h1>
      <p className="admin__muted">
        Paste the reference a person quotes from their run page. You see the
        queue&rsquo;s tasks and the model calls for that run, never the
        person&rsquo;s steps or text.
      </p>
      <form
        className="console__find"
        onSubmit={(event) => {
          event.preventDefault();
          setParams(text.trim() ? { run: text.trim() } : {});
        }}
      >
        <TextField
          label="Run reference"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        <ActionButton
          type="submit"
          variant="primary"
          disabled={busy || !text.trim()}
        >
          Find
        </ActionButton>
      </form>

      <div role="status">{busy ? <p>Looking{"…"}</p> : null}</div>
      {error && (
        <div role="alert" className="admin__message admin__message--error">
          <p>{error}</p>
        </div>
      )}

      {trace && !trace.found && (
        <p>
          Nothing in the queue or the model log mentions this run. It may be too
          old (finished tasks are cleared after a few days), or the reference is
          wrong.
        </p>
      )}

      {trace?.found && (
        <>
          <h2>Tasks</h2>
          {trace.tasks.length === 0 ? (
            <p>
              No task is recorded for this run. Finished tasks are cleared after
              a few days.
            </p>
          ) : (
            <DataTable caption="Queue tasks for this run">
              <thead>
                <tr>
                  <th scope="col">Task</th>
                  <th scope="col">State</th>
                  <th scope="col" className="num">
                    Tries
                  </th>
                  <th scope="col">Last error</th>
                  <th scope="col">Account</th>
                  <th scope="col">Started</th>
                </tr>
              </thead>
              <tbody>
                {trace.tasks.map((task) => (
                  <tr key={task.id}>
                    <th scope="row">{task.task_type}</th>
                    <td>{task.state.replaceAll("_", " ")}</td>
                    <td className="num">
                      {task.attempts} of {task.max_attempts}
                    </td>
                    <td>{task.last_error ?? "None"}</td>
                    <td>{task.owner_email ?? "None"}</td>
                    <td>{formatDateTime(task.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
          <h2>Model calls</h2>
          {trace.calls.length === 0 ? (
            <p>No model call was made in this run.</p>
          ) : (
            <DataTable caption="Model calls for this run (metadata only, no text is stored)">
              <thead>
                <tr>
                  <th scope="col">Operation</th>
                  <th scope="col">Model</th>
                  <th scope="col">Prompt version</th>
                  <th scope="col" className="num">
                    Tokens in and out
                  </th>
                  <th scope="col" className="num">
                    Estimated cost
                  </th>
                  <th scope="col" className="num">
                    Time
                  </th>
                  <th scope="col">Result</th>
                </tr>
              </thead>
              <tbody>
                {trace.calls.map((call, index) => (
                  <tr key={index}>
                    <th scope="row">{call.purpose}</th>
                    <td>
                      {call.provider} / {call.model}
                    </td>
                    <td>{call.prompt_version ?? "None"}</td>
                    <td className="num">
                      {formatNumber(call.input_tokens)} and{" "}
                      {formatNumber(call.output_tokens)}
                    </td>
                    <td className="num">{formatCost(call.cost_usd)}</td>
                    <td className="num">{formatNumber(call.latency_ms)} ms</td>
                    <td>
                      {call.status === "ok"
                        ? "Succeeded"
                        : `Failed${call.error_class ? ` (${call.error_class})` : ""}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </>
      )}
    </>
  );
}
