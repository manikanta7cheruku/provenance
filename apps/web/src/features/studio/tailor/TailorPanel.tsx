import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../../lib/api";
import {
  acceptSuggestion,
  editSuggestion,
  fetchTailorJobs,
  fetchTailoring,
  rejectSuggestion,
  startTailoring,
} from "../../../lib/studio-api";
import type { TailorSuggestion, Tailoring } from "../../../lib/studio-api";
import { useAsync } from "../../../lib/useAsync";
import { ActionButton, Notice, Select, Skeleton, TextArea } from "../../../ui";
import { pairLines } from "./diff";
import type { Piece } from "./diff";
import "./tailor.css";

const POLL_MS = 1500;

function Pieces({ pieces }: { pieces: Piece[] }) {
  return (
    <>
      {pieces.map((p, i) =>
        p.kind === "added" ? (
          <ins key={i}>{p.text}</ins>
        ) : p.kind === "removed" ? (
          <del key={i}>{p.text}</del>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </>
  );
}

/** The old and the new wording side by side, with the words that changed marked. */
function SideBySide({ s }: { s: TailorSuggestion }) {
  const rows = pairLines(s.before_lines, s.after_lines);
  const bullets = s.kind === "bullets";
  return (
    <div className="tailor__diff">
      <div>
        <p className="tailor__side">Your resume now</p>
        <ul className={bullets ? "tailor__lines" : "tailor__lines tailor__lines--plain"}>
          {rows.map((r, i) => (r.before ? <li key={i}><Pieces pieces={r.before} /></li> : null))}
        </ul>
      </div>
      <div>
        <p className="tailor__side">Suggested</p>
        <ul className={bullets ? "tailor__lines" : "tailor__lines tailor__lines--plain"}>
          {rows.map((r, i) => (r.after ? <li key={i}><Pieces pieces={r.after} /></li> : null))}
        </ul>
      </div>
    </div>
  );
}

function Checks({ s }: { s: TailorSuggestion }) {
  const missing = s.claims.filter((c) => !c.supported).map((c) => c.text);
  const found = s.claims.filter((c) => c.supported);
  if (s.claims.length === 0) return <p className="tailor__ok">No new facts: this only rewords what you already wrote.</p>;
  return (
    <div className="tailor__checks">
      {missing.length > 0 ? (
        <p className="tailor__bad">
          <strong>Not found in your resume or evidence:</strong> {missing.join(", ")}.
        </p>
      ) : (
        <p className="tailor__ok">
          <strong>Every fact checked:</strong> {found.map((c) => c.text).join(", ")} {found.length === 1 ? "was" : "were"} found in your own words.
        </p>
      )}
    </div>
  );
}

function Card({
  resumeId,
  tailoringId,
  s,
  onChange,
  onAccept,
  disabled,
}: {
  resumeId: string;
  tailoringId: string;
  s: TailorSuggestion;
  onChange: (next: TailorSuggestion) => void;
  onAccept: (s: TailorSuggestion) => Promise<void>;
  disabled: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(s.after_lines.join("\n"));
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const pending = s.status === "pending";

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setProblem(null);
    try {
      await action();
    } catch (caught) {
      setProblem(caught instanceof ApiError ? (caught.fields ? Object.values(caught.fields)[0] ?? caught.message : caught.message) : "That did not work. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    run(async () => {
      const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
      onChange(await editSuggestion(resumeId, tailoringId, s.id, lines));
      setEditing(false);
    });

  const hintId = `tailor-hint-${s.id}`;
  return (
    <li className={`tailor__card${s.blocked && pending ? " is-blocked" : ""}`}>
      <h4 className="tailor__title">{s.label}</h4>
      {s.status !== "pending" ? (
        <p className="tailor__done" role="status">
          {s.status === "accepted" ? "Applied to your resume." : "Rejected. Your resume was not changed."}
        </p>
      ) : null}
      {editing ? (
        <TextArea
          label={`Edit the suggested wording for ${s.label}`}
          hint={s.kind === "bullets" ? "One bullet per line." : "One paragraph."}
          rows={Math.max(3, s.after_lines.length + 1)}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      ) : (
        <SideBySide s={s} />
      )}
      {s.reason ? <p className="tailor__reason">{s.reason}</p> : null}
      {s.requirements.length > 0 ? (
        <p className="tailor__meta">
          <strong>Helps with:</strong> {s.requirements.map((r) => r.text).join("; ")}
        </p>
      ) : null}
      {s.citations.length > 0 ? (
        <details className="tailor__evidence">
          <summary>Evidence this uses ({s.citations.length})</summary>
          <ul>
            {s.citations.map((c) => (
              <li key={c.chunk_id}>{c.quote}</li>
            ))}
          </ul>
        </details>
      ) : null}
      <Checks s={s} />
      {s.edited ? <p className="tailor__meta">You edited this suggestion. It was checked again.</p> : null}
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}
      {pending ? (
        <div className="tailor__actions">
          {editing ? (
            <>
              <ActionButton variant="primary" onClick={() => void save()} disabled={busy}>
                Save my edit
              </ActionButton>
              <ActionButton
                onClick={() => {
                  setEditing(false);
                  setText(s.after_lines.join("\n"));
                }}
                disabled={busy}
              >
                Cancel edit
              </ActionButton>
            </>
          ) : (
            <>
              <ActionButton
                variant="primary"
                aria-label={`Accept change, ${s.label}`}
                aria-describedby={s.blocked ? hintId : undefined}
                disabled={busy || disabled || s.blocked}
                onClick={() => void run(() => onAccept(s))}
              >
                Accept
              </ActionButton>
              <ActionButton aria-label={`Edit change, ${s.label}`} disabled={busy || disabled} onClick={() => setEditing(true)}>
                Edit
              </ActionButton>
              <ActionButton
                aria-label={`Reject change, ${s.label}`}
                disabled={busy || disabled}
                onClick={() => void run(async () => onChange(await rejectSuggestion(resumeId, tailoringId, s.id)))}
              >
                Reject
              </ActionButton>
            </>
          )}
        </div>
      ) : null}
      {s.blocked && pending ? (
        <p id={hintId} className="tailor__meta">
          This cannot be applied while it adds something your evidence does not support. Edit it to remove that, reject it, or add the missing detail to your profile and ask again. You can
          also type it into your resume yourself.
        </p>
      ) : null}
    </li>
  );
}

interface TailorPanelProps {
  resumeId: string;
  /** Saves any typing first, so the change is made to what is on the screen. */
  flush: () => Promise<void>;
  getRevision: () => number;
  /** Called after a change was applied, so the editor shows the new wording. */
  onApplied: () => Promise<void>;
}

/** Tailor the resume to a job that has been checked against the person's profile. */
export function TailorPanel({ resumeId, flush, getRevision, onApplied }: TailorPanelProps) {
  const jobs = useAsync((signal) => fetchTailorJobs(signal), []);
  const [jobId, setJobId] = useState("");
  const [tailoring, setTailoring] = useState<Tailoring | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const firstJob = jobs.data?.[0]?.job_id ?? "";
  const chosen = jobId || firstJob;

  useEffect(() => {
    if (!chosen) return;
    const controller = new AbortController();
    setTailoring(null);
    fetchTailoring(resumeId, chosen, controller.signal)
      .then(setTailoring)
      .catch(() => undefined);
    return () => controller.abort();
  }, [resumeId, chosen]);

  const working = tailoring?.ui_state === "working";
  useEffect(() => {
    if (!working || !chosen) return;
    const timer = window.setInterval(() => {
      fetchTailoring(resumeId, chosen)
        .then((next) => next && setTailoring(next))
        .catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [working, resumeId, chosen]);

  async function begin() {
    setBusy(true);
    setProblem(null);
    try {
      await flush();
      setTailoring(await startTailoring(resumeId, chosen));
      setMessage("Looking for changes that your evidence supports.");
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "Suggestions could not be started. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  const replace = useCallback((next: TailorSuggestion) => {
    setTailoring((t) => (t ? { ...t, suggestions: t.suggestions.map((s) => (s.id === next.id ? next : s)) } : t));
  }, []);

  const accept = useCallback(
    async (s: TailorSuggestion) => {
      if (!tailoring) return;
      await flush();
      const done = await acceptSuggestion(resumeId, tailoring.id, s.id, getRevision());
      replace(done.suggestion);
      await onApplied();
      setMessage(`Applied the change to ${s.label}. Earlier wording is kept in Earlier versions.`);
    },
    [tailoring, flush, resumeId, getRevision, replace, onApplied],
  );

  if (jobs.loading) return <Skeleton label="Loading your checked jobs" lines={2} />;
  if (jobs.error) {
    return (
      <Notice tone="danger" title="Jobs could not be loaded">
        <p>{jobs.error.message}</p>
      </Notice>
    );
  }
  if (!jobs.data || jobs.data.length === 0) {
    return (
      <p className="tailor__empty">
        Suggestions are made for a job you have checked against your profile. Paste a job in <Link to="/opportunities">Opportunities</Link> and check it, then come back here.
      </p>
    );
  }

  const pending = tailoring?.suggestions.filter((s) => s.status === "pending") ?? [];
  return (
    <div className="tailor">
      <p className="studio__lead">
        Pick a job. You get suggested rewordings of your bullets and summary, each with the reason and the evidence it uses. Anything that adds a fact your profile does not support is
        blocked. Nothing changes in your resume until you accept it.
      </p>
      <div className="tailor__start">
        <Select label="Job" value={chosen} onChange={(e) => setJobId(e.target.value)}>
          {jobs.data.map((j) => (
            <option key={j.job_id} value={j.job_id}>
              {j.title ?? "Untitled job"}
              {j.company ? `, ${j.company}` : ""}
            </option>
          ))}
        </Select>
        <ActionButton variant="primary" onClick={() => void begin()} disabled={busy || working}>
          {working ? "Looking for changes" : tailoring ? "Suggest again" : "Suggest changes"}
        </ActionButton>
      </div>
      <div role="status" className="visually-hidden">
        {message}
      </div>
      {working ? <p role="status">This takes a moment. You can keep editing.</p> : null}
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}
      {tailoring?.ui_state === "failed" ? (
        <Notice tone="danger" title="No suggestions this time">
          <p>{tailoring.error_message}</p>
        </Notice>
      ) : null}
      {tailoring?.ui_state === "ready" ? (
        <>
          <h3 className="tailor__heading">
            {tailoring.suggestions.length === 0
              ? "No changes suggested"
              : `${tailoring.suggestions.length} suggested ${tailoring.suggestions.length === 1 ? "change" : "changes"}, ${pending.length} waiting`}
          </h3>
          {tailoring.suggestions.length === 0 ? (
            <p>Nothing in your bullets or summary would be clearly better for this job, using only what your evidence supports.</p>
          ) : (
            <ul className="tailor__list">
              {tailoring.suggestions.map((s) => (
                <Card key={s.id} resumeId={resumeId} tailoringId={tailoring.id} s={s} onChange={replace} onAccept={accept} disabled={busy} />
              ))}
            </ul>
          )}
          {tailoring.unclaimed.length > 0 ? (
            <details className="tailor__gaps">
              <summary>Not added to your resume ({tailoring.unclaimed.length})</summary>
              <p>The job asks for these, but nothing in your profile confirms them, so no suggestion claims them.</p>
              <ul>
                {tailoring.unclaimed.map((g) => (
                  <li key={g.text}>
                    {g.text}. <span className="tailor__meta">{g.reason}</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
