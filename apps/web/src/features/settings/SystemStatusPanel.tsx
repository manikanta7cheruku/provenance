import { useSystemStatus } from "../../lib/system-status";
import { Button, Notice, Status, type Tone } from "../../ui";

const CHECKS: Record<string, { tone: Tone; label: string }> = {
  ok: { tone: "ok", label: "Working" },
  fail: { tone: "danger", label: "Not reachable" },
  behind: { tone: "warn", label: "Needs migration" },
  unknown: { tone: "warn", label: "Could not check" },
};

function describe(value: string): { tone: Tone; label: string } {
  return CHECKS[value] ?? { tone: "warn", label: "Unknown" };
}

export function SystemStatusPanel() {
  const { state, refresh } = useSystemStatus();

  if (state.kind === "loading") {
    return <p role="status">Checking the API...</p>;
  }

  if (state.kind === "unreachable") {
    return (
      <Notice tone="danger" title="The web app could not reach the API.">
        <p>
          Nothing is stored in this browser yet, so no data is at risk. This page does not retry on
          its own.
        </p>
        <p>Detail: {state.message}</p>
        <Button onClick={refresh}>Check again</Button>
      </Notice>
    );
  }

  const { status } = state;
  const database = describe(status.checks.database);
  const migrations = describe(status.checks.migrations);

  return (
    <>
      <table className="data-table">
        <caption className="visually-hidden">System status</caption>
        <tbody>
          <tr>
            <th scope="row">Service</th>
            <td>
              {status.service} {status.version}
            </td>
          </tr>
          <tr>
            <th scope="row">Environment</th>
            <td>{status.environment}</td>
          </tr>
          <tr>
            <th scope="row">Database</th>
            <td>
              <Status tone={database.tone} label={database.label} />
            </td>
          </tr>
          <tr>
            <th scope="row">Migrations</th>
            <td>
              <Status tone={migrations.tone} label={migrations.label} />
            </td>
          </tr>
        </tbody>
      </table>
      <p className="actions">
        <Button onClick={refresh}>Check again</Button>
      </p>
    </>
  );
}
