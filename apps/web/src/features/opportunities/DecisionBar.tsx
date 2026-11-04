import { useState } from "react";
import { ApiError } from "../../lib/api";
import { daysAgo } from "../../lib/format";
import { ACTION_HELP, decideJob, decisionTone } from "../../lib/workbench-api";
import type { Decision, DecisionAction, DecisionResult } from "../../lib/workbench-api";
import { ActionButton, Notice, Status } from "../../ui";
import { ApplyDialog } from "./ApplyDialog";

interface DecisionBarProps {
  job: { id: string; title: string | null; company: string | null };
  decision: Decision;
  /** Called with what the server answered, after any action. */
  onDecided: (action: DecisionAction, result: DecisionResult) => void;
  /** The job page has no toast, so the bar shows its own Undo for the last action. */
  ownUndo?: boolean;
}

export function jobLabel(job: { title: string | null; company: string | null }): string {
  return `${job.title ?? "this job"}${job.company ? ` at ${job.company}` : ""}`;
}

/** The decision on one job: its state, and exactly the actions the server offers now. */
export function DecisionBar({ job, decision, onDecided, ownUndo = false }: DecisionBarProps) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [undo, setUndo] = useState<{ action: DecisionAction; label: string } | null>(null);
  const label = jobLabel(job);

  async function run(action: DecisionAction, day?: string) {
    setBusy(true);
    setProblem(null);
    try {
      const result = await decideJob(job.id, action, day);
      setUndo(result.undo && result.undo_label ? { action: result.undo, label: result.undo_label } : null);
      setApplying(false);
      onDecided(action, result);
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "Something unexpected happened. Nothing was changed.");
      setApplying(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="decision">
      <p className="decision__state" role="status">
        <Status tone={decisionTone(decision.state)} label={decision.state_label} />
        {decision.state === "applied" && decision.applied_at ? (
          <span className="job__explanation">
            {" "}
            on {new Date(decision.applied_at).toLocaleDateString()} ({daysAgo(decision.applied_at)})
          </span>
        ) : null}
      </p>
      {problem ? (
        <Notice tone="warn">
          <p>{problem}</p>
        </Notice>
      ) : null}
      <div className="decision__actions">
        {decision.actions.map((entry) => (
          <ActionButton
            key={entry.action}
            disabled={busy}
            title={ACTION_HELP[entry.action]}
            aria-label={`${entry.label}: ${label}`}
            onClick={() => (entry.action === "mark_applied" ? setApplying(true) : void run(entry.action))}
          >
            {entry.label}
          </ActionButton>
        ))}
      </div>
      {ownUndo && undo ? (
        <p className="decision__undo" role="status">
          Done.{" "}
          <ActionButton disabled={busy} onClick={() => void run(undo.action)}>
            {undo.label}
          </ActionButton>
        </p>
      ) : null}
      <ApplyDialog
        open={applying}
        label={label}
        busy={busy}
        onCancel={() => setApplying(false)}
        onConfirm={(day) => void run("mark_applied", day)}
      />
    </div>
  );
}
