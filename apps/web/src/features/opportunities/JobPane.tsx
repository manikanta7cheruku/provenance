import { Link } from "react-router-dom";
import { describeBand, describeEligibility, describeJobState } from "../../lib/states";
import type { Band } from "../../lib/states";
import type { DecisionAction, DecisionResult, WorkRow } from "../../lib/workbench-api";
import { Status } from "../../ui";
import { DecisionBar } from "./DecisionBar";
import { NoteBox } from "./NoteBox";
import { acquisitionLabel, workLine } from "./labels";

/** The selected job beside the list: what it is, what you decided, and what you can do next. */
export function JobPane({
  row,
  onDecided,
  onNoteSaved,
}: {
  row: WorkRow;
  onDecided: (row: WorkRow, action: DecisionAction, result: DecisionResult) => void;
  onNoteSaved: () => void;
}) {
  const state = row.reading !== "ready" ? describeJobState(row.reading) : null;
  const eligibility = row.eligibility ? describeEligibility(row.eligibility) : null;
  const band = row.band ? describeBand(row.band as Band) : null;
  return (
    <aside className="bench__pane" aria-label="Selected job">
      <h3 className="bench__panetitle">{row.title ?? "Untitled posting"}</h3>
      <p className="row-sub">{[row.company ?? "Company not stated", workLine({ work_mode: row.work_mode, location: row.location })].filter(Boolean).join(" · ")}</p>
      <dl className="bench__facts">
        <div>
          <dt>Fit</dt>
          <dd>{band ? <Status tone={band.tone} label={band.label} /> : "Not checked yet. Open the job to check it against your evidence."}</dd>
        </div>
        <div>
          <dt>Can you take it</dt>
          <dd>
            {state ? (
              <Status tone={state.tone} label={state.label} />
            ) : eligibility ? (
              <Status tone={eligibility.tone} label={eligibility.label} />
            ) : (
              "Not known yet"
            )}
          </dd>
        </div>
        <div>
          <dt>Where it came from</dt>
          <dd>
            {row.source_name}. {acquisitionLabel(row.acquisition_method)}.
          </dd>
        </div>
      </dl>
      <DecisionBar
        job={row}
        decision={row.decision}
        onDecided={(action, result) => onDecided(row, action, result)}
      />
      <NoteBox jobId={row.id} note={row.decision.note} onSaved={onNoteSaved} />
      <p>
        <Link to={`/opportunities/${row.id}`}>Open the full job</Link>
      </p>
    </aside>
  );
}
