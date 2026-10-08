import { useSystemStatus } from "../lib/system-status";
import { Status } from "../ui";

/** Compact system status shown at the foot of the navigation. Announced politely on change. */
export function NavStatus() {
  const { state } = useSystemStatus();
  let status = <Status tone="neutral" label="Checking system" />;
  if (state.kind === "unreachable") status = <Status tone="danger" label="API unreachable" />;
  if (state.kind === "loaded") {
    status = state.status.ready ? (
      <Status tone="ok" label="System ready" />
    ) : (
      <Status tone="warn" label="System not ready" />
    );
  }
  return <div role="status">{status}</div>;
}
