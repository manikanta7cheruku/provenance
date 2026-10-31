import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { deleteJob, fetchJob, reanalyzeJob } from "../../lib/jobs-api";
import type { JobDetail, JobGate, JobRequirement } from "../../lib/jobs-api";
import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { describeEligibility, describeJobState, isJobBusy } from "../../lib/states";
import { useAsync } from "../../lib/useAsync";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { ActionButton, ConfirmDialog, Notice, PageHeader, Section, Skeleton, Status } from "../../ui";
import { EvidenceCheck } from "./EvidenceCheck";
import { acquisitionLabel, CATEGORY_LABELS, FACT_LABELS, factText, workLine } from "./labels";
import "./opportunities.css";

const REFRESH_MS = 2000;

function Quote({ label, children }: { label: string; children: string }) {
  return (
    <div className="voice-posting">
      <p className="voice-posting__label">{label}</p>
      <blockquote className="voice-posting__quote">{children}</blockquote>
    </div>
  );
}

function Gate({ gate }: { gate: JobGate }) {
  const info = describeEligibility(gate.state);
  return (
    <li className="gate">
      <p className="gate__head">
        <Status tone={info.tone} label={`${gate.label}: ${info.label}`} />
      </p>
      <p className="gate__reason">{gate.reason}</p>
      {gate.posting_quote ? <Quote label="The posting says">{gate.posting_quote}</Quote> : null}
      {gate.state === "requires_user_input" ? (
        <p className="gate__action">
          <Link to="/profile">Answer this in your profile</Link>
        </p>
      ) : null}
    </li>
  );
}

function RequirementGroup({ title, items }: { title: string; items: JobRequirement[] }) {
  if (items.length === 0) return null;
  return (
    <div className="reqs-group">
      <h3 className="reqs-group__title">
        {title} <span className="reqs-group__count">{items.length}</span>
      </h3>
      <ol className="reqs">
        {items.map((req) => (
          <li key={req.id} className="req-item">
            <p className="req-item__text">
              {req.text}
              <span className="req-item__kind">{CATEGORY_LABELS[req.category] ?? req.category}</span>
            </p>
            <Quote label="The posting says">{req.quote}</Quote>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Ready({ job }: { job: JobDetail }) {
  const eligibility = job.eligibility_detail;
  const overall = eligibility ? describeEligibility(eligibility.state) : null;
  const required = job.requirements.filter((r) => r.kind === "required");
  const preferred = job.requirements.filter((r) => r.kind === "preferred");
  const facts = Object.entries(job.facts);
  return (
    <>
      {eligibility && overall ? (
        <Section title="Can you take this job?">
          <p className="job__overall">
            <Status tone={overall.tone} label={overall.label} />
          </p>
          <p className="job__note">
            These checks use only what the posting says and what you told us. A blocker is stated
            as a blocker. It is never averaged into a score.
          </p>
          <ul className="gates">
            {eligibility.gates.map((gate) => (
              <Gate key={gate.gate} gate={gate} />
            ))}
          </ul>
        </Section>
      ) : null}

      {facts.length > 0 ? (
        <Section title="What the posting states">
          <dl className="facts">
            {facts.map(([key, fact]) => (
              <div key={key} className="facts__row">
                <dt>{FACT_LABELS[key] ?? key}</dt>
                <dd>
                  {factText(key, fact)}
                  <span className="facts__quote">{`"${fact.quote}"`}</span>
                </dd>
              </div>
            ))}
          </dl>
        </Section>
      ) : null}

      <Section title="What it asks for">
        {job.requirements_dropped + job.facts_dropped > 0 ? (
          <Notice tone="info">
            <p>
              {job.requirements_dropped + job.facts_dropped} suggested{" "}
              {job.requirements_dropped + job.facts_dropped === 1 ? "item was" : "items were"} not
              found in the posting text, so {job.requirements_dropped + job.facts_dropped === 1 ? "it was" : "they were"}{" "}
              left out.
            </p>
          </Notice>
        ) : null}
        <RequirementGroup title="Required" items={required} />
        <RequirementGroup title="Nice to have" items={preferred} />
      </Section>
    </>
  );
}

export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const job = useAsync((signal) => fetchJob(jobId, signal), [jobId]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const data = job.data;
  useDocumentTitle(data?.title ?? "Job posting");

  const reading = data ? isJobBusy(data.ui_state) : false;
  useEffect(() => {
    if (!reading) return;
    const timer = window.setInterval(job.reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [reading, job.reload]);

  async function act(action: () => Promise<unknown>, after?: () => void) {
    setBusy(true);
    setProblem(null);
    try {
      await action();
      after?.();
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "Something unexpected happened. Your data is safe. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (job.error instanceof ApiError && job.error.status === 404) {
    return (
      <>
        <PageHeader title="Job not found" description="This posting does not exist, or it was deleted." />
        <p>
          <Link to="/opportunities">Back to your jobs</Link>
        </p>
      </>
    );
  }
  if (job.error) {
    return (
      <>
        <PageHeader title="Job posting" />
        <Notice tone="danger" title="This job could not be loaded">
          <p>{job.error.message} Nothing was changed.</p>
          <p>
            <ActionButton onClick={job.reload}>Try again</ActionButton>
          </p>
        </Notice>
      </>
    );
  }
  if (!data) {
    return (
      <>
        <PageHeader title="Job posting" />
        <Skeleton label="Loading the job" lines={5} />
      </>
    );
  }

  const state = describeJobState(data.ui_state);
  const fromRouter = (location.state as { duplicate?: boolean } | null)?.duplicate === true;
  return (
    <>
      <p className="job__back">
        <Link to="/opportunities">Back to your jobs</Link>
      </p>
      <PageHeader
        title={data.title ?? "Untitled posting"}
        description={[data.company ?? "Company not stated", workLine(data)].filter(Boolean).join(" · ")}
      />
      <p className="job__source">
        {`Source: ${data.source_name}. ${acquisitionLabel(data.acquisition_method)} on ${formatDateTime(data.created_at)}. Private to you.`}
        {data.source_url ? (
          <>
            {" "}
            <a href={data.source_url} target="_blank" rel="noopener noreferrer">
              Open the original (new tab)
            </a>
          </>
        ) : null}
      </p>
      {fromRouter ? (
        <Notice tone="info">
          <p>You pasted this job before, so nothing was read again. Here it is.</p>
        </Notice>
      ) : null}

      <p role="status" className="job__state">
        <Status tone={state.tone} label={state.label} />
        <span className="job__explanation">{state.explanation}</span>
      </p>

      {data.ui_state === "reading" ? <Skeleton label="Reading the posting" lines={4} /> : null}
      {data.ui_state === "failed" ? (
        <Notice tone="danger" title="This posting could not be read">
          <p>{data.error_message}</p>
          <p>You can read it again, or delete it and paste a fuller version.</p>
        </Notice>
      ) : null}
      {data.ui_state === "ready" ? <Ready job={data} /> : null}
      {data.ui_state === "ready" ? <EvidenceCheck jobId={data.id} /> : null}

      <Section title="The posting">
        <details className="posting">
          <summary>Show the text you pasted</summary>
          <pre className="posting__text">{data.text}</pre>
        </details>
      </Section>

      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}
      <div className="job__actions">
        {data.can_retry ? (
          <ActionButton
            onClick={() => void act(() => reanalyzeJob(data.id), job.reload)}
            disabled={busy}
          >
            Read it again
          </ActionButton>
        ) : null}
        <ActionButton onClick={() => setConfirmDelete(true)} disabled={busy}>
          Delete this job
        </ActionButton>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this job?"
        confirmLabel="Delete job"
        danger
        busy={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() =>
          void act(() => deleteJob(data.id), () => {
            setConfirmDelete(false);
            navigate("/opportunities");
          })
        }
      >
        <p>The pasted text and what we read from it are removed. Your profile is not affected.</p>
      </ConfirmDialog>
    </>
  );
}
