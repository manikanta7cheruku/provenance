import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchEvaluation, fetchEvaluations } from "../../lib/admin-api";
import type { EvalDetail, EvalMetric, EvalRun } from "../../lib/admin-api";
import { formatDateTime, formatNumber } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable, Select, Status } from "../../ui";
import type { Tone } from "../../ui";

const STATUS: Record<EvalMetric["status"], { tone: Tone; label: string }> = {
  ok: { tone: "ok", label: "Within its limit" },
  new: { tone: "neutral", label: "No baseline yet" },
  regressed: { tone: "danger", label: "Worse than its baseline" },
  below_limit: { tone: "danger", label: "Outside its limit" },
};

const SUITE_LABELS: Record<string, string> = {
  extraction: "Extraction (grounding)",
  eligibility: "Eligibility",
  verdicts: "Evidence verdicts",
  bands: "Scoring bands",
  ranking: "Ranking",
  claims: "Claim checking",
  llm_extraction: "Extraction by the real model",
};

function runLabel(run: EvalRun): string {
  return `${formatDateTime(run.created_at)}, ${run.suite} suite, ${run.git_sha ?? "no commit"}, ${run.passed ? "passed" : "failed"}`;
}

function num(value: number | null, digits = 4): string {
  return value === null ? "None" : value.toFixed(digits);
}

function signed(value: number | null): string {
  if (value === null) return "None";
  if (value === 0) return "No change";
  return `${value > 0 ? "+" : ""}${value.toFixed(4)}`;
}

function Metrics({ detail }: { detail: EvalDetail }) {
  const comparing = detail.against !== null;
  return (
    <DataTable caption="Every metric against its limit and its baseline">
      <thead>
        <tr>
          <th scope="col">Metric</th>
          <th scope="col" className="num">
            Value
          </th>
          <th scope="col" className="num">
            Baseline
          </th>
          <th scope="col" className="num">
            Limit
          </th>
          <th scope="col" className="num">
            Cases
          </th>
          <th scope="col">State</th>
          {comparing && (
            <th scope="col" className="num">
              Against the other run
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {detail.metrics.map((m) => (
          <tr key={m.name}>
            <th scope="row">{m.label}</th>
            <td className="num">{num(m.value)}</td>
            <td className="num">{num(m.baseline)}</td>
            <td className="num">
              {m.direction === "higher" ? "at least " : "at most "}
              {m.limit.toFixed(2)}
            </td>
            <td className="num">{formatNumber(m.cases)}</td>
            <td>
              <Status
                tone={STATUS[m.status].tone}
                label={STATUS[m.status].label}
              />
            </td>
            {comparing && <td className="num">{signed(m.change)}</td>}
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function Failures({ detail }: { detail: EvalDetail }) {
  const [suite, setSuite] = useState("");
  const names = Array.from(new Set(detail.failures.map((f) => f.suite)));
  const shown = suite
    ? detail.failures.filter((f) => f.suite === suite)
    : detail.failures;
  if (detail.failures.length === 0) return <p>No case failed in this run.</p>;
  return (
    <>
      <Select
        label="Show failures from"
        value={suite}
        onChange={(event) => setSuite(event.target.value)}
      >
        <option value="">All suites</option>
        {names.map((n) => (
          <option key={n} value={n}>
            {SUITE_LABELS[n] ?? n}
          </option>
        ))}
      </Select>
      <DataTable
        caption={`Failed cases (${shown.length} of ${detail.run.failure_count})`}
      >
        <thead>
          <tr>
            <th scope="col">Suite</th>
            <th scope="col">Case</th>
            <th scope="col">Expected</th>
            <th scope="col">Got</th>
            <th scope="col">Note</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((f, index) => (
            <tr key={`${f.case_id}-${index}`}>
              <td>{SUITE_LABELS[f.suite] ?? f.suite}</td>
              <th scope="row">{f.case_id}</th>
              <td>{f.expected}</td>
              <td>{f.got}</td>
              <td>{f.note || "None"}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {detail.run.failure_count > detail.failures.length && (
        <p className="admin__muted">
          Only the first {detail.failures.length} failures are stored.{" "}
          {detail.run.failure_count} failed in all.
        </p>
      )}
    </>
  );
}

/** Are we regressing: the stored evaluation runs, one run in full, and a comparison between two. */
export function EvaluationPage() {
  const heading = usePageChrome("Evaluation");
  const [params, setParams] = useSearchParams();
  const list = useAsync((signal) => fetchEvaluations(signal), []);
  const runs = list.data?.runs ?? [];
  const chosen =
    params.get("run") ??
    list.data?.latest.deterministic?.id ??
    runs[0]?.id ??
    "";
  const against = params.get("against") ?? "";

  const [detail, setDetail] = useState<EvalDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!chosen) {
      setDetail(null);
      return;
    }
    let live = true;
    setError(null);
    fetchEvaluation(chosen, against || null)
      .then((result) => live && setDetail(result))
      .catch(
        (caught) =>
          live &&
          setError(
            caught instanceof Error
              ? caught.message
              : "The run could not be loaded.",
          ),
      );
    return () => {
      live = false;
    };
  }, [chosen, against]);

  function choose(next: Record<string, string>) {
    const merged = { run: chosen, against, ...next };
    setParams(Object.fromEntries(Object.entries(merged).filter(([, v]) => v)));
  }

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        Evaluation
      </h1>
      <p className="admin__muted">
        Are we regressing? The deterministic suite checks our own rules
        (grounding, eligibility, evidence verdicts, scoring, ranking and claim
        checking) against a labeled set of 100 synthetic postings. It costs
        nothing and runs on every build. The model suite measures a real model
        on the same postings and costs tokens, so it runs on demand. The
        postings are invented, so a pass shows our checks behave as written, not
        that a real model reads real postings well.
      </p>

      {list.loading && <p>Loading{"…"}</p>}
      {list.error && (
        <div role="alert" className="admin__message">
          <p>{list.error.message}</p>
          <ActionButton onClick={list.reload}>Try again</ActionButton>
        </div>
      )}

      {list.data && runs.length === 0 && (
        <div className="admin__message">
          <p>
            No evaluation has been stored yet. Run{" "}
            <code>python -m pv_eval run --store</code> and reload this page.
          </p>
        </div>
      )}

      {runs.length > 0 && (
        <div className="console__find">
          <Select
            label="Run"
            value={chosen}
            onChange={(event) => choose({ run: event.target.value })}
          >
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {runLabel(run)}
              </option>
            ))}
          </Select>
          <Select
            label="Compare with"
            value={against}
            onChange={(event) => choose({ against: event.target.value })}
          >
            <option value="">Nothing, just the baseline</option>
            {runs
              .filter((run) => run.id !== chosen)
              .map((run) => (
                <option key={run.id} value={run.id}>
                  {runLabel(run)}
                </option>
              ))}
          </Select>
        </div>
      )}

      {error && (
        <div role="alert" className="admin__message admin__message--error">
          <p>{error}</p>
        </div>
      )}

      {detail && (
        <>
          <p role="status" className="console__headline">
            <Status
              tone={detail.run.passed ? "ok" : "danger"}
              label={detail.run.passed ? "Passed" : "Did not pass"}
            />{" "}
            <span>
              {detail.run.passed
                ? "Every metric is inside its limit and no worse than its baseline."
                : `Needs a look: ${detail.run.regressions.join(", ") || "see the metrics"}.`}
            </span>
          </p>
          <dl className="admin__counts">
            <div>
              <dt>Cases</dt>
              <dd>{formatNumber(detail.run.case_count)}</dd>
            </div>
            <div>
              <dt>Failed cases</dt>
              <dd>{formatNumber(detail.run.failure_count)}</dd>
            </div>
            <div>
              <dt>Dataset</dt>
              <dd>{detail.run.dataset_version}</dd>
            </div>
            <div>
              <dt>Commit</dt>
              <dd>{detail.run.git_sha ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{detail.run.model ?? "None (rules only)"}</dd>
            </div>
            <div>
              <dt>Made</dt>
              <dd>{formatDateTime(detail.run.created_at)}</dd>
            </div>
          </dl>
          <p className="admin__muted">
            Versions:{" "}
            {Object.entries(detail.versions)
              .map(([k, v]) => `${k.replaceAll("_", " ")} ${v}`)
              .join(", ")}
            .
          </p>
          {detail.against && (
            <p>Compared with the run of {runLabel(detail.against)}.</p>
          )}

          <h2>Metrics</h2>
          <Metrics detail={detail} />

          <h2>Suites</h2>
          <DataTable caption="Cases run and failed in each suite">
            <thead>
              <tr>
                <th scope="col">Suite</th>
                <th scope="col" className="num">
                  Cases
                </th>
                <th scope="col" className="num">
                  Failed
                </th>
              </tr>
            </thead>
            <tbody>
              {detail.suites.map((s) => (
                <tr key={s.name}>
                  <th scope="row">{SUITE_LABELS[s.name] ?? s.name}</th>
                  <td className="num">{formatNumber(s.cases)}</td>
                  <td className="num">{formatNumber(s.failed)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>

          <h2>Failed cases</h2>
          <Failures detail={detail} key={detail.run.id} />
        </>
      )}

      <h2>A learned ranker</h2>
      <p>
        Not adopted. The scorer is deterministic and explainable, and a learned
        ranker may only reorder results when it beats the rules by at least 5
        points of agreement with people, on held-out labels, from at least 1,000
        labels given by at least 30 people. Today there are far fewer labels, so
        the answer is no (ADR-0054).
      </p>

      <h2>How to run it</h2>
      <ul>
        <li>
          <code>python -m pv_eval run --store</code> runs the deterministic
          suites and stores the result here.
        </li>
        <li>
          <code>python -m pv_eval run --llm --store</code> runs the real model
          on the same postings (needs the model key and costs tokens).
        </li>
        <li>
          <code>python -m pv_eval run --update-baseline</code> accepts
          today&rsquo;s numbers as the new baseline. That is a decision, so
          review the change before you commit it.
        </li>
      </ul>
    </>
  );
}
