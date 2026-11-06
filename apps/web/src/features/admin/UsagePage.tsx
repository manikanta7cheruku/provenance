import { useState } from "react";
import { fetchUsage } from "../../lib/admin-api";
import type { Usage, UsageRow } from "../../lib/admin-api";
import { formatCost, formatNumber } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable, Select } from "../../ui";

function Table({
  caption,
  first,
  rows,
}: {
  caption: string;
  first: string;
  rows: UsageRow[];
}) {
  if (rows.length === 0) return <p>No model calls in this period.</p>;
  return (
    <DataTable caption={caption}>
      <thead>
        <tr>
          <th scope="col">{first}</th>
          <th scope="col" className="num">
            Calls
          </th>
          <th scope="col" className="num">
            Failed
          </th>
          <th scope="col" className="num">
            Input tokens
          </th>
          <th scope="col" className="num">
            Output tokens
          </th>
          <th scope="col" className="num">
            Estimated cost
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            <th scope="row">{row.key}</th>
            <td className="num">{formatNumber(row.calls)}</td>
            <td className="num">{formatNumber(row.errors)}</td>
            <td className="num">{formatNumber(row.input_tokens)}</td>
            <td className="num">{formatNumber(row.output_tokens)}</td>
            <td className="num">{formatCost(row.cost_usd)}</td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function Totals({ data }: { data: Usage }) {
  return (
    <dl className="admin__counts">
      <div>
        <dt>Estimated cost</dt>
        <dd>{formatCost(data.cost_usd)}</dd>
      </div>
      <div>
        <dt>Model calls</dt>
        <dd>{formatNumber(data.calls)}</dd>
      </div>
      <div>
        <dt>Failed calls</dt>
        <dd>{formatNumber(data.errors)}</dd>
      </div>
      <div>
        <dt>Tokens in and out</dt>
        <dd>
          {formatNumber(data.input_tokens)} and{" "}
          {formatNumber(data.output_tokens)}
        </dd>
      </div>
      <div>
        <dt>Accounts that used it</dt>
        <dd>{formatNumber(data.accounts)}</dd>
      </div>
      <div>
        <dt>Average call time</dt>
        <dd>
          {data.average_latency_ms === null
            ? "Not measured"
            : `${formatNumber(data.average_latency_ms)} ms`}
        </dd>
      </div>
    </dl>
  );
}

/** What does it cost. Aggregates only: no account is named. */
export function UsagePage() {
  const heading = usePageChrome("Cost and usage");
  const [days, setDays] = useState<7 | 30>(7);
  const { data, error, loading, reload } = useAsync(
    (signal) => fetchUsage(days, signal),
    [days],
  );

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        Cost and usage
      </h1>
      <p className="admin__muted">
        Model calls, tokens and estimated cost, added up by model, by operation
        and by day. Estimates use the prices set in configuration, so they show
        where the money goes, not the provider&rsquo;s invoice. No account is
        named.
      </p>
      <Select
        label="Period"
        value={String(days)}
        onChange={(event) => setDays(event.target.value === "30" ? 30 : 7)}
      >
        <option value="7">Last 7 days</option>
        <option value="30">Last 30 days</option>
      </Select>

      {loading && <p>Loading{"…"}</p>}
      {error && (
        <div role="alert" className="admin__message">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}

      {data && (
        <>
          <Totals data={data} />
          <p>
            {data.daily_spend_ceiling_usd > 0
              ? `A daily spend ceiling of $${data.daily_spend_ceiling_usd.toFixed(2)} is set. The console alerts at 80 percent of it.`
              : "No daily spend ceiling is set, so spend raises no alert. Set LLM_DAILY_SPEND_CEILING_USD to add one."}
          </p>
          {data.highest_account_share !== null && data.accounts > 1 && (
            <p>
              The account that used the most made up{" "}
              {Math.round(data.highest_account_share * 100)} percent of the
              cost.
            </p>
          )}
          <h2>By model</h2>
          <Table
            caption={`Cost by model, last ${data.days} days`}
            first="Model"
            rows={data.by_model}
          />
          <h2>By operation</h2>
          <Table
            caption={`Cost by operation, last ${data.days} days`}
            first="Operation"
            rows={data.by_purpose}
          />
          <h2>By day</h2>
          <Table
            caption={`Cost by day, last ${data.days} days`}
            first="Day (UTC)"
            rows={data.by_day}
          />
        </>
      )}
    </>
  );
}
