import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../lib/api";
import {
  answerQuestion,
  fetchAnalysis,
  giveFeedback,
  skipQuestion,
  startAnalysis,
} from "../../lib/analysis-api";
import type { Analysis, Citation, Gap, Question, VerdictRow } from "../../lib/analysis-api";
import {
  describeAnalysisState,
  describeBand,
  describeVerdict,
  isAnalysisBusy,
} from "../../lib/states";
import { useAsync } from "../../lib/useAsync";
import { ActionButton, Notice, Section, Skeleton, Status, TextArea } from "../../ui";
import { CATEGORY_LABELS } from "./labels";

const REFRESH_MS = 2000;
const ANSWER_MAX = 1000;

const CONFIDENCE: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  none: "No evidence found",
};

function sourceText(c: Citation): string {
  if (c.source === "answer") return "From your answer";
  return c.entry_type ? `From your profile, ${c.entry_type} entry` : "From your profile";
}

function Feedback({
  value,
  label,
  busy,
  onChoose,
}: {
  value: "right" | "wrong" | null;
  label: string;
  busy: boolean;
  onChoose: (answer: "right" | "wrong") => void;
}) {
  return (
    <div className="feedback" role="group" aria-label={label}>
      <span className="feedback__label">Was this right?</span>
      <button type="button" className="feedback__btn" aria-pressed={value === "right"} disabled={busy} onClick={() => onChoose("right")}>
        Yes, this is right
      </button>
      <button type="button" className="feedback__btn" aria-pressed={value === "wrong"} disabled={busy} onClick={() => onChoose("wrong")}>
        No, this is wrong
      </button>
    </div>
  );
}

function VerdictItem({
  row,
  busy,
  onFeedback,
}: {
  row: VerdictRow;
  busy: boolean;
  onFeedback: (answer: "right" | "wrong") => void;
}) {
  const info = row.verdict ? describeVerdict(row.verdict) : null;
  const tag = row.kind === "preferred" ? "Nice to have" : (CATEGORY_LABELS[row.category] ?? row.category);
  const head = (
    <>
      <span className="verdict__text">{row.requirement}</span>
      <span className="verdict__tag">{tag}</span>
      {info ? <Status tone={info.tone} label={info.label} /> : <Status tone="neutral" label="Waiting" />}
      {row.confidence && row.verdict !== "not_verified" ? (
        <span className="verdict__meta">
          {row.evidence_kind === "inferred" ? "Inferred" : "Direct"} evidence, {CONFIDENCE[row.confidence]?.toLowerCase()}
        </span>
      ) : null}
    </>
  );
  if (!row.verdict) {
    return <li className="verdict verdict--waiting">{head}</li>;
  }
  return (
    <li className="verdict">
      <details>
        <summary className="verdict__summary">{head}</summary>
        <div className="verdict__body">
          <div className="voice-posting">
            <p className="voice-posting__label">The posting says</p>
            <blockquote className="voice-posting__quote">{row.posting_quote}</blockquote>
          </div>
          {row.citations.length > 0 ? (
            row.citations.map((c) => (
              <div className="voice-evidence" key={c.chunk_id}>
                <p className="voice-evidence__label">{sourceText(c)}</p>
                <blockquote className="voice-evidence__quote">{c.quote}</blockquote>
                {c.changed ? (
                  <p className="verdict__warn">This entry changed after the check. Check again to be sure.</p>
                ) : null}
              </div>
            ))
          ) : (
            <p className="verdict__none">No evidence from your profile is cited for this requirement.</p>
          )}
          {row.reason ? (
            <p className="verdict__reason">
              <strong>{row.citations.length > 0 ? "The reader's note: " : "Why: "}</strong>
              {row.reason}
            </p>
          ) : null}
          {row.capped ? (
            <p className="verdict__reason">
              The evidence here is reasoned, not stated, so it can count only as partly met.
            </p>
          ) : null}
          <Feedback
            value={row.feedback}
            label={`Feedback on: ${row.requirement}`}
            busy={busy}
            onChoose={onFeedback}
          />
        </div>
      </details>
    </li>
  );
}

function QuestionCard({
  question,
  busy,
  onAnswer,
  onSkip,
}: {
  question: Question;
  busy: boolean;
  onAnswer: (text: string) => Promise<string | null>;
  onSkip: () => void;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | undefined>();
  const [attempt, setAttempt] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);

  // After a refused answer, move focus to the field so keyboard and screen reader users land on it.
  useEffect(() => {
    if (attempt > 0) formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [attempt]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) {
      setError("Write a short answer, or skip this question.");
      setAttempt((n) => n + 1);
      return;
    }
    if (trimmed.length > ANSWER_MAX) {
      setError(`Keep it under ${ANSWER_MAX} characters.`);
      setAttempt((n) => n + 1);
      return;
    }
    setError(undefined);
    const problem = await onAnswer(trimmed);
    if (problem) {
      setError(problem);
      setAttempt((n) => n + 1);
    } else setText("");
  }

  return (
    <form ref={formRef} className="question" onSubmit={submit} noValidate>
      <p className="question__for">About: {question.requirement}</p>
      <TextArea
        label={question.question}
        hint="Saved as evidence while this job exists. Deleting the job deletes your answer."
        rows={3}
        value={text}
        error={error}
        onChange={(event) => setText(event.target.value)}
      />
      <div className="question__actions">
        <ActionButton type="submit" disabled={busy}>
          Use this answer
        </ActionButton>
        <ActionButton onClick={onSkip} disabled={busy}>
          Skip, leave it unverified
        </ActionButton>
      </div>
    </form>
  );
}

function Headline({
  analysis,
  busy,
  onFeedback,
}: {
  analysis: Analysis;
  busy: boolean;
  onFeedback: (answer: "right" | "wrong") => void;
}) {
  const score = analysis.score;
  if (!score) return null;
  const band = describeBand(score.band);
  return (
    <div className="headline">
      <p className="headline__band">
        <Status tone={band.tone} label={band.label} />
      </p>
      {score.band !== "not_eligible" ? (
        <p className="headline__count">
          {score.met + score.partial} of {score.required_total} required{" "}
          {score.required_total === 1 ? "requirement" : "requirements"} supported
        </p>
      ) : null}
      <ul className="headline__reasons">
        {score.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      <p className="headline__version">Scoring {score.scoring_version}. Numbers are counts, not percentages.</p>
      <Feedback
        value={analysis.recommendation_feedback}
        label="Feedback on this recommendation"
        busy={busy}
        onChoose={onFeedback}
      />
    </div>
  );
}

function Gaps({ gaps }: { gaps: Gap[] }) {
  if (gaps.length === 0) return null;
  return (
    <div className="gaps">
      <h3 className="gaps__title">What would change this</h3>
      <p className="job__note">
        For each required item that is not fully supported, this is what would count as proof. Nothing here
        says you lack the skill.
      </p>
      <ol className="gaps__list">
        {gaps.map((gap) => (
          <li key={gap.requirement_id} className="gap">
            <p className="gap__req">{gap.requirement}</p>
            <p>
              <strong>Proof that counts: </strong>
              {gap.proof_needed}
            </p>
            <p>
              <strong>Next step: </strong>
              {gap.next_step}{" "}
              <Link to="/profile">Open your profile</Link>
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function EvidenceCheck({ jobId }: { jobId: string }) {
  const analysis = useAsync((signal) => fetchAnalysis(jobId, signal), [jobId]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const data = analysis.data;
  const working = data ? isAnalysisBusy(data.ui_state) : false;

  useEffect(() => {
    if (!working) return;
    const timer = window.setInterval(analysis.reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [working, analysis.reload]);

  async function act(action: () => Promise<unknown>): Promise<string | null> {
    setBusy(true);
    setProblem(null);
    try {
      await action();
      analysis.reload();
      return null;
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? (caught.fields.answer ?? caught.message)
          : "Something unexpected happened. Your data is safe. Try again.";
      setProblem(message);
      return message;
    } finally {
      setBusy(false);
    }
  }

  if (analysis.error) {
    return (
      <Section title="Your evidence">
        <Notice tone="danger" title="The evidence check could not be loaded">
          <p>{analysis.error.message} Nothing was changed.</p>
          <p>
            <ActionButton onClick={analysis.reload}>Try again</ActionButton>
          </p>
        </Notice>
      </Section>
    );
  }
  if (!data) {
    return (
      <Section title="Your evidence">
        <Skeleton label="Loading the evidence check" lines={3} />
      </Section>
    );
  }

  const state = describeAnalysisState(data.ui_state);
  const pending = data.questions.filter((q) => q.status === "pending");
  const canRun = data.ui_state === "not_started" || data.ui_state === "ready" || data.ui_state === "failed";
  const runLabel =
    data.ui_state === "ready" ? "Check again" : data.ui_state === "failed" ? "Continue checking" : "Check my evidence";

  return (
    <Section title="Your evidence">
      <p role="status" className="job__state">
        <Status tone={state.tone} label={state.label} />
        <span className="job__explanation">
          {data.ui_state === "working" ? `${data.checked} of ${data.total} checked. ` : ""}
          {state.explanation}
        </span>
      </p>

      {data.ui_state === "ready" ? (
        <p className="job__explanation">
          Next: <Link to="/studio">tailor your resume to this job</Link>. Suggestions only use what this check confirmed.
        </p>
      ) : null}
      {data.ui_state === "failed" && data.error_message ? (
        <Notice tone="danger">
          <p>{data.error_message}</p>
        </Notice>
      ) : null}
      {data.stale ? (
        <Notice tone="warn">
          <p>Something you cited changed after this check. Check again to bring it up to date.</p>
        </Notice>
      ) : null}
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}

      <Headline
        analysis={data}
        busy={busy}
        onFeedback={(answer) => void act(() => giveFeedback(jobId, { requirement_id: null, answer }))}
      />

      {pending.map((q) => (
        <QuestionCard
          key={q.id}
          question={q}
          busy={busy}
          onAnswer={(text) => act(() => answerQuestion(jobId, q.id, text))}
          onSkip={() => void act(() => skipQuestion(jobId, q.id))}
        />
      ))}

      {data.verdicts.length > 0 && data.ui_state !== "not_started" ? (
        <ol className="verdicts">
          {data.verdicts.map((row) => (
            <VerdictItem
              key={row.requirement_id}
              row={row}
              busy={busy}
              onFeedback={(answer) =>
                void act(() => giveFeedback(jobId, { requirement_id: row.requirement_id, answer }))
              }
            />
          ))}
        </ol>
      ) : null}

      {data.gate_requirements.length > 0 && data.ui_state !== "not_started" ? (
        <p className="job__note">
          {data.gate_requirements.length === 1
            ? "One requirement is decided by the eligibility checks above, not by your evidence: "
            : `${data.gate_requirements.length} requirements are decided by the eligibility checks above, not by your evidence: `}
          {data.gate_requirements.map((g) => g.requirement).join("; ")}.
        </p>
      ) : null}

      <Gaps gaps={data.gaps} />

      {canRun ? (
        <div className="job__actions">
          <ActionButton onClick={() => void act(() => startAnalysis(jobId))} disabled={busy || !data.can_start}>
            {runLabel}
          </ActionButton>
          {!data.can_start && data.blocker ? <p className="job__note">{data.blocker}</p> : null}
        </div>
      ) : null}
    </Section>
  );
}
