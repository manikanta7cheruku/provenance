import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { ActionButton, PageHeader, SegmentedControl, Section, Status, TextArea } from "../../ui";
import { BAND_TONE, SAMPLE_GAPS, SAMPLE_JOBS, SAMPLE_REQUIREMENTS, VERDICT_TONE } from "./fixtures";
import type { SampleEvidence, SampleRequirement } from "./fixtures";

const FEEDBACK_OPTIONS = [
  { value: "yes", label: "Yes" },
  { value: "partly", label: "Partly" },
  { value: "no", label: "No" },
] as const;

/** The four kinds of statement on this screen look and read differently, so they are never confused. */
function Voice({
  kind,
  label,
  children,
}: {
  kind: "posting" | "evidence" | "inference" | "suggestion";
  label: string;
  children: ReactNode;
}) {
  return (
    <div className={`voice voice--${kind}`}>
      <p className="voice__label">{label}</p>
      <div className="voice__body">{children}</div>
    </div>
  );
}

function EvidenceItem({ item }: { item: SampleEvidence }) {
  if (item.kind === "Missing") {
    return (
      <Voice kind="evidence" label="Missing evidence">
        <p>No statement in your profile supports this requirement.</p>
      </Voice>
    );
  }
  const kind = item.kind === "Inferred" ? "inference" : "evidence";
  const label =
    item.kind === "Inferred"
      ? "Inferred, not stated"
      : item.kind === "Conflicting"
        ? "Conflicts with other evidence"
        : "Direct evidence";
  return (
    <Voice kind={kind} label={label}>
      <blockquote className="voice__quote">{item.quote}</blockquote>
      <p className="voice__meta">
        {item.from}. {item.provenance}.
      </p>
    </Voice>
  );
}

function Requirement({ requirement, defaultOpen }: { requirement: SampleRequirement; defaultOpen: boolean }) {
  return (
    <details className="req" open={defaultOpen}>
      <summary className="req__summary">
        <span className="req__text">
          {requirement.text}
          <span className="req__kind">{requirement.required ? "Required" : "Preferred"}</span>
        </span>
        <span className="req__verdict">
          <Status tone={VERDICT_TONE[requirement.verdict]} label={requirement.verdict} />
          <span className="req__confidence">
            {requirement.confidence === "Not enough evidence" ? "Not enough evidence" : `${requirement.confidence} confidence`}
          </span>
        </span>
      </summary>
      <div className="req__detail">
        <Voice kind="posting" label="The posting says">
          <blockquote className="voice__quote">{requirement.postingQuote}</blockquote>
        </Voice>
        {requirement.evidence.map((item, index) => (
          <EvidenceItem key={index} item={item} />
        ))}
        <p className="req__why">
          <strong>Why this confidence.</strong> {requirement.confidenceWhy}
        </p>
        {requirement.missing ? (
          <p className="req__why">
            <strong>What is missing.</strong> {requirement.missing}
          </p>
        ) : null}
        {requirement.suggestion ? (
          <Voice kind="suggestion" label="Suggestion, not a fact">
            <p>{requirement.suggestion}</p>
          </Voice>
        ) : null}
      </div>
    </details>
  );
}

/**
 * Prototype of the trust screen with sample data. A user can see the requirement, whether they
 * meet it, the proof, how confident the system is and why, what is missing and what to do next,
 * without logs or developer tools. The real screen is built in checkpoint 1.9.
 */
export function JobDetailPrototype() {
  useDocumentTitle("Job detail prototype");
  const job = SAMPLE_JOBS[0];
  const [feedback, setFeedback] = useState<"yes" | "partly" | "no">("yes");
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(false);
  if (!job) throw new Error("Sample data is missing");

  return (
    <>
      <p className="back">
        <Link to="/design/workbench">Back to opportunities</Link>
      </p>
      <PageHeader
        title={job.title}
        description={`${job.company} · ${job.place} · ${job.workMode}. Prototype with sample data.`}
      />

      <p className="provenance-line">
        Source: {job.source}. {job.acquisition}. Visibility: private to you.
      </p>

      <Section title="Summary">
        <p className="summary__fit">
          <Status tone={BAND_TONE[job.band]} label={job.band} />
        </p>
        <p className="summary__text">{job.reason}</p>
        <p className="summary__note">
          This sentence is assembled by code from the stored results. The score never hides an eligibility check.
        </p>
      </Section>

      <Section title="Eligibility checks">
        <ul className="gates">
          {job.gates.map((gate) => (
            <li key={gate.name}>
              <Status
                tone={gate.result === "Passed" ? "ok" : gate.result === "Blocked" ? "danger" : "warn"}
                label={`${gate.name}: ${gate.result}`}
              />
              <p className="gates__detail">{gate.detail}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Requirements, one by one">
        <details className="legend">
          <summary>How to read this page</summary>
          <div className="legend__body">
            <Voice kind="posting" label="The posting says">
              <p>Text copied from the job posting.</p>
            </Voice>
            <Voice kind="evidence" label="Direct evidence">
              <p>Something you stated in your profile, with where it came from.</p>
            </Voice>
            <Voice kind="inference" label="Inferred, not stated">
              <p>A reasonable reading of your evidence. It never counts as a full match.</p>
            </Voice>
            <Voice kind="suggestion" label="Suggestion, not a fact">
              <p>Advice from the assistant. You decide whether it is true for you.</p>
            </Voice>
          </div>
        </details>
        <div className="reqs">
          {SAMPLE_REQUIREMENTS.map((requirement, index) => (
            <Requirement key={requirement.id} requirement={requirement} defaultOpen={index === 1} />
          ))}
        </div>
      </Section>

      <Section title="How to close the gaps">
        <ol className="gaps">
          {SAMPLE_GAPS.map((gap) => (
            <li key={gap.title}>
              <h3 className="gaps__title">{gap.title}</h3>
              <p>{gap.why}</p>
              <Voice kind="suggestion" label="Suggestion, not a fact">
                <p>{gap.action}</p>
              </Voice>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Was this analysis right?">
        <div className="feedback">
          <SegmentedControl
            legend="Was this analysis right?"
            options={FEEDBACK_OPTIONS}
            value={feedback}
            onChange={(value) => {
              setFeedback(value);
              setSent(false);
            }}
          />
          <TextArea
            label="What was wrong or missing? (optional)"
            hint="Do not paste personal details. This helps improve the analysis."
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
          />
          <ActionButton variant="primary" onClick={() => setSent(true)}>
            Send feedback
          </ActionButton>
          <p role="status" className="feedback__status">
            {sent ? "Thanks. Your answer was recorded for this analysis." : ""}
          </p>
        </div>
      </Section>
    </>
  );
}
