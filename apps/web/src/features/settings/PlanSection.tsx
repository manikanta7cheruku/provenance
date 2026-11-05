import { formatDateTime } from "../../lib/format";
import {
  describeQuota,
  fetchPlan,
  formatDay,
  limitWords,
} from "../../lib/plan-api";
import type { PlanState, Quota } from "../../lib/plan-api";
import { useAsync } from "../../lib/useAsync";
import { ActionButton, Notice, Section, Skeleton, Status } from "../../ui";

function Meter({ quota }: { quota: Quota }) {
  const tone =
    quota.state === "reached"
      ? "danger"
      : quota.state === "near"
        ? "warn"
        : "ok";
  return (
    <li className="plan__meter">
      <div className="plan__meterhead">
        <strong>{quota.label}</strong>
        <Status tone={tone} label={describeQuota(quota)} />
      </div>
      {quota.limit !== null ? (
        <progress
          className={`plan__bar plan__bar--${quota.state}`}
          max={Math.max(quota.limit, 1)}
          value={Math.min(quota.used, Math.max(quota.limit, 1))}
          aria-label={`${quota.label}: ${describeQuota(quota)}`}
        />
      ) : null}
      <p className="field__hint">{quota.help}</p>
    </li>
  );
}

function Comparison({ data }: { data: PlanState }) {
  const rows = [
    ...data.quotas.map((q) => ({
      key: q.unit,
      label: q.label,
      value: (id: string) =>
        limitWords(data.plans.find((p) => p.id === id)?.limits[q.unit]),
    })),
    {
      key: "resumes",
      label: "Resumes kept",
      value: (id: string) =>
        String(data.plans.find((p) => p.id === id)?.resumes ?? ""),
    },
    {
      key: "exports",
      label: "PDFs kept for each resume",
      value: (id: string) =>
        String(data.plans.find((p) => p.id === id)?.exports_per_resume ?? ""),
    },
  ];
  return (
    <div className="data-table__scroll">
      <table className="data-table">
        <caption className="data-table__caption">
          What each plan includes each month
        </caption>
        <thead>
          <tr>
            <th scope="col">Included</th>
            {data.plans.map((p) => (
              <th key={p.id} scope="col" className="num">
                {p.label}
                {p.current ? " (yours)" : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <th scope="row">{row.label}</th>
              {data.plans.map((p) => (
                <td key={p.id} className="num">
                  {row.value(p.id)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Your plan and what you have used this month. Reading it is always possible, whatever you have used. */
export function PlanSection() {
  const { data, error, loading, reload } = useAsync(
    (signal) => fetchPlan(signal),
    [],
  );
  if (error) {
    return (
      <Section title="Your plan and usage">
        <Notice tone="danger" title="Your plan could not be loaded">
          <p>{error.message}</p>
          <p>
            <ActionButton onClick={reload}>Try again</ActionButton>
          </p>
        </Notice>
      </Section>
    );
  }
  if (loading || !data) {
    return (
      <Section title="Your plan and usage">
        <Skeleton label="Loading your plan" lines={3} />
      </Section>
    );
  }
  return (
    <Section title="Your plan and usage">
      <p>
        You are on the <strong>{data.plan_label}</strong> plan. Usage counts
        from {formatDay(`${data.period_start}T00:00:00Z`)} and starts again on{" "}
        {formatDay(data.resets_at)}.
      </p>
      <p className="field__hint">
        Reading what your evidence shows for a job you have already checked,
        editing, and exporting what you have are never counted.
      </p>
      <ul className="plan__meters" aria-label="Usage this month">
        {data.quotas.map((q) => (
          <Meter key={q.unit} quota={q} />
        ))}
      </ul>
      <p>
        <strong>Resumes:</strong> {data.resumes_used} of {data.resumes_limit}{" "}
        kept. <strong>PDFs kept for each resume:</strong>{" "}
        {data.exports_per_resume}.
      </p>
      <Comparison data={data} />
      {data.provisional ? (
        <p className="field__hint">
          These limits are starting points. They will be set from what things
          really cost, and you will be told before they change.
        </p>
      ) : null}
      <Notice tone="info" title="Changing plan">
        <p>{data.payments.message}</p>
      </Notice>
      {data.recent.length > 0 ? (
        <details className="plan__recent">
          <summary>What was counted recently</summary>
          <ul>
            {data.recent.map((event, index) => (
              <li key={`${event.at}-${index}`}>
                {event.label}, {event.amount}{" "}
                {event.amount === 1 ? "unit" : "units"},{" "}
                {formatDateTime(event.at)}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Section>
  );
}
