import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import { deleteDraft, describeClaimKind, fetchDrafts, isWriting, saveDraft, startDraft } from "../../lib/drafts-api";
import type { Draft, DraftKind, Drafts as DraftsData } from "../../lib/drafts-api";
import { useAsync } from "../../lib/useAsync";
import { ActionButton, Button, ConfirmDialog, Notice, Section, Select, Skeleton, Status, TextArea, TextField } from "../../ui";

const REFRESH_MS = 2000;
const CUSTOM = "__custom__";

function title(draft: Draft): string {
  return draft.kind === "cover_note" ? "Cover note" : draft.question;
}

function DraftCard({
  jobId,
  draft,
  onChanged,
  onProblem,
}: {
  jobId: string;
  draft: Draft;
  onChanged: () => void;
  onProblem: (text: string) => void;
}) {
  const [value, setValue] = useState(draft.body);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState<string | undefined>();
  const [confirm, setConfirm] = useState<"again" | "delete" | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => setValue(draft.body), [draft.id, draft.body]);

  const changed = value.trim() !== draft.body.trim();
  const unsupported = draft.claims.filter((c) => !c.supported);

  async function save() {
    setBusy(true);
    setError(undefined);
    setSaved("");
    try {
      await saveDraft(jobId, draft.id, value);
      setSaved("Saved.");
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? (caught.fields.body ?? caught.message) : "The draft could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function again(replace: boolean) {
    setBusy(true);
    try {
      await startDraft(jobId, draft.kind, draft.question, replace);
      setConfirm(null);
      onChanged();
    } catch (caught) {
      setConfirm(null);
      onProblem(caught instanceof ApiError ? caught.message : "The draft could not be started again.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await deleteDraft(jobId, draft.id);
      setConfirm(null);
      onChanged();
    } catch (caught) {
      setConfirm(null);
      onProblem(caught instanceof ApiError ? caught.message : "The draft could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 3000);
    } catch {
      onProblem("The text could not be copied. Select it and copy it yourself.");
    }
  }

  return (
    <article className="draft" aria-label={`Draft: ${title(draft)}`}>
      <h3 className="draft__title">{title(draft)}</h3>
      <p className="draft__meta">
        <Status tone="warn" label="Draft" />
        {draft.origin === "edited" ? <span> Edited by you.</span> : <span> Written by AI from your evidence.</span>}
      </p>

      {draft.ui_state === "working" ? <Skeleton label={`Writing: ${title(draft)}`} lines={4} /> : null}

      {draft.ui_state === "failed" ? (
        <Notice tone="danger" title="This draft could not be written">
          <p>{draft.error_message}</p>
          {draft.body ? <p>The earlier text is still below.</p> : null}
        </Notice>
      ) : null}

      {draft.ui_state !== "working" && (draft.body || draft.ui_state === "ready") ? (
        <>
          <TextArea
            label="Draft text"
            hint="Edit it freely. Every claim is checked again when you save."
            rows={draft.kind === "cover_note" ? 10 : 6}
            value={value}
            error={error}
            onChange={(event) => setValue(event.target.value)}
          />
          <p className="draft__row">
            <Button variant="secondary" busy={busy} disabled={!changed} onClick={() => void save()}>
              Save changes
            </Button>
            <ActionButton onClick={() => void copy()}>Copy text</ActionButton>
            <span role="status">{copied ? "Copied." : saved}</span>
            <span className="draft__count">{value.trim() ? value.trim().split(/\s+/).length : 0} words</span>
          </p>

          {unsupported.length > 0 ? (
            <Notice tone="warn" title="Check these before you use this draft">
              <p>These are not in your evidence or in the job posting:</p>
              <ul>
                {unsupported.map((c) => (
                  <li key={c.text}>
                    <strong>{c.text}</strong> ({describeClaimKind(c.kind)})
                  </li>
                ))}
              </ul>
              <p>Remove them, or add the evidence to your profile and check the job again.</p>
            </Notice>
          ) : draft.claims.length > 0 ? (
            <p className="draft__ok">Every number, name and tool in this draft is in your evidence or in the job posting.</p>
          ) : null}

          {draft.evidence.length > 0 ? (
            <details className="draft__evidence">
              <summary>The evidence this draft may use ({draft.evidence.length})</summary>
              <ul>
                {draft.evidence.map((item, index) => (
                  <li key={index}>
                    {item.text}
                    <span className="row-sub">
                      {item.source === "answer" ? "From your answer" : "From your profile"}
                      {item.cited ? ". Used in the draft." : "."}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </>
      ) : null}

      <p className="draft__row">
        <ActionButton
          disabled={busy || draft.ui_state === "working"}
          onClick={() => (draft.origin === "edited" ? setConfirm("again") : void again(false))}
        >
          Write it again<span className="visually-hidden">: {title(draft)}</span>
        </ActionButton>
        <ActionButton disabled={busy} onClick={() => setConfirm("delete")}>
          Delete<span className="visually-hidden">: {title(draft)}</span>
        </ActionButton>
      </p>

      <ConfirmDialog
        open={confirm === "again"}
        title="Write this draft again?"
        confirmLabel="Replace my edits"
        danger
        busy={busy}
        onCancel={() => setConfirm(null)}
        onConfirm={() => void again(true)}
      >
        <p>You edited this draft. Writing it again replaces your edits with new text.</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={confirm === "delete"}
        title="Delete this draft?"
        confirmLabel="Delete draft"
        danger
        busy={busy}
        onCancel={() => setConfirm(null)}
        onConfirm={() => void remove()}
      >
        <p>{title(draft)} is deleted. Your job and evidence are not changed.</p>
      </ConfirmDialog>
    </article>
  );
}

/** Cover notes and answers for one job, written from your evidence and always labelled as drafts. */
export function Drafts({ jobId }: { jobId: string }) {
  const drafts = useAsync((signal) => fetchDrafts(jobId, signal), [jobId]);
  const data: DraftsData | null = drafts.data;
  const [choice, setChoice] = useState("why_role");
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>();

  const writing = isWriting(data);
  const { reload } = drafts;
  useEffect(() => {
    if (!writing) return;
    const timer = window.setInterval(reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [writing, reload]);

  async function ask(kind: DraftKind, question = "") {
    setBusy(true);
    setProblem(null);
    setFieldError(undefined);
    try {
      await startDraft(jobId, kind, question);
      reload();
    } catch (caught) {
      if (caught instanceof ApiError && caught.fields.question) setFieldError(caught.fields.question);
      else setProblem(caught instanceof ApiError ? caught.message : "The draft could not be started. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  const questionText = choice === CUSTOM ? custom : (data?.questions.find((q) => q.key === choice)?.text ?? "");
  const hasCover = data?.drafts.some((d) => d.kind === "cover_note") ?? false;

  return (
    <Section title="Application drafts">
      {drafts.error ? (
        <Notice tone="danger" title="Drafts could not be loaded">
          <p>{drafts.error.message} Nothing was changed.</p>
          <p>
            <ActionButton onClick={reload}>Try again</ActionButton>
          </p>
        </Notice>
      ) : !data ? (
        <Skeleton label="Loading drafts" lines={3} />
      ) : (
        <>
          <Notice tone="info">
            <p>{data.label}</p>
          </Notice>
          {data.blocker ? (
            <Notice tone="warn">
              <p>{data.blocker}</p>
            </Notice>
          ) : (
            <div className="draft__ask">
              <p>
                <Button variant="secondary" busy={busy} disabled={hasCover || data.drafts.length >= data.max_drafts} onClick={() => void ask("cover_note")}>
                  Write a cover note
                </Button>
              </p>
              <Select label="Answer a common question" value={choice} onChange={(event) => setChoice(event.target.value)}>
                {data.questions.map((q) => (
                  <option key={q.key} value={q.key}>
                    {q.text}
                  </option>
                ))}
                <option value={CUSTOM}>Another question</option>
              </Select>
              {choice === CUSTOM ? (
                <TextField
                  label="Your question"
                  hint="Type the question the employer asks."
                  value={custom}
                  error={fieldError}
                  onChange={(event) => setCustom(event.target.value)}
                />
              ) : null}
              <p>
                <Button variant="secondary" busy={busy} disabled={data.drafts.length >= data.max_drafts} onClick={() => void ask("answer", questionText)}>
                  Write an answer
                </Button>
              </p>
              {data.drafts.length >= data.max_drafts ? <p className="job__note">You have {data.max_drafts} drafts for this job, the most you can keep. Delete one to write another.</p> : null}
            </div>
          )}
          {problem ? (
            <Notice tone="warn">
              <p>{problem}</p>
            </Notice>
          ) : null}
          {data.drafts.length === 0 && !data.blocker ? (
            <p className="job__note">No drafts yet. Each one uses only what your evidence supports for this job.</p>
          ) : null}
          {data.drafts.map((draft) => (
            <DraftCard key={draft.id} jobId={jobId} draft={draft} onChanged={reload} onProblem={setProblem} />
          ))}
        </>
      )}
    </Section>
  );
}
