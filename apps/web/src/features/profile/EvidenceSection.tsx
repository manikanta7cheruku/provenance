import { useState } from "react";
import type { FormEvent } from "react";
import { fetchEvidenceStatus, searchEvidence } from "../../lib/evidence-api";
import type { EvidenceHit, EvidenceSearch, EvidenceStatus } from "../../lib/evidence-api";
import { useAsync } from "../../lib/useAsync";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { ActionButton, Button, Notice, Section, Skeleton, TextField } from "../../ui";

const TYPE_LABELS: Record<string, string> = {
  education: "Education",
  work: "Work experience",
  internship: "Internship",
  project: "Project",
  skill: "Skill",
  certification: "Certification",
  achievement: "Achievement",
  link: "Link",
};

/** One plain sentence about what the search can do right now. */
export function describeStatus(status: EvidenceStatus): string {
  if (status.indexed === 0) return "Nothing to search yet. Add entries above and they appear here.";
  const entries = `${status.indexed} ${status.indexed === 1 ? "entry is" : "entries are"} searchable by keyword.`;
  if (!status.meaning_search_configured) {
    return `${entries} Meaning search is off until an AI key is set up.`;
  }
  if (status.pending === 0) return `${entries} Meaning search is ready.`;
  return `${entries} Meaning search is still indexing: ${status.embedded} of ${status.indexed} done.`;
}

export function matchedLabel(hit: EvidenceHit): string {
  const both = hit.matched_by.includes("keyword") && hit.matched_by.includes("meaning");
  if (both) return "Found by keyword and by meaning";
  return hit.matched_by.includes("meaning") ? "Found by meaning" : "Found by keyword";
}

interface EvidenceSectionProps {
  /** Changes when the entries changed, so the counts reload. */
  version: number;
}

export function EvidenceSection({ version }: EvidenceSectionProps) {
  const status = useAsync((signal) => fetchEvidenceStatus(signal), [version]);
  const form = useFormSubmit();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<EvidenceSearch | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!query.trim()) errors.query = "Enter a word, a phrase or a question.";
    await form.submit(errors, async () => {
      setResult(await searchEvidence(query.trim()));
      status.reload();
    });
  }

  if (status.error) {
    return (
      <Section title="Search your evidence">
        <Notice tone="danger" title="Search could not be loaded">
          <p>{status.error.message} Nothing was changed.</p>
          <p>
            <ActionButton onClick={status.reload}>Try again</ActionButton>
          </p>
        </Notice>
      </Section>
    );
  }
  if (!status.data) {
    return (
      <Section title="Search your evidence">
        <Skeleton label="Loading search" lines={2} />
      </Section>
    );
  }

  return (
    <Section title="Search your evidence">
      <p className="entries__lead">
        This is how a job is checked against you: each requirement is looked up in your own entries.
        Try it here to see what a job would find. It searches only what you have stored.
      </p>
      <p className="evidence__status" role="status">
        {describeStatus(status.data)}
      </p>

      <form ref={form.formRef} className="evidence__form" onSubmit={onSubmit} noValidate>
        <TextField
          label="Search your entries"
          hint="Words, a phrase in quotes, or a short question. Put a minus before a word to leave it out."
          type="search"
          value={query}
          error={form.fieldErrors.query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked || status.data.indexed === 0}>
          Search
        </Button>
      </form>
      {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}

      <div aria-live="polite" className="evidence__results">
        {result ? <Results result={result} /> : null}
      </div>
    </Section>
  );
}

function Results({ result }: { result: EvidenceSearch }) {
  return (
    <>
      <p className="evidence__count">
        {result.hits.length === 0
          ? "No entry matches that."
          : `${result.hits.length} ${result.hits.length === 1 ? "match" : "matches"}, best first.`}
      </p>
      {result.note ? (
        <Notice tone="info">
          <p>{result.note}</p>
        </Notice>
      ) : null}
      {result.hits.length === 0 ? (
        <p className="evidence__empty">
          Try fewer or different words. A requirement a job states in other words may still be
          matched once meaning search is on.
        </p>
      ) : (
        <ol className="evidence__list">
          {result.hits.map((hit) => (
            <li key={hit.chunk_id} className="evidence__hit">
              <p className="evidence__type">
                {TYPE_LABELS[hit.entry_type ?? ""] ?? "Entry"} {"·"} From your profile
              </p>
              <p className="evidence__text">{hit.text}</p>
              <p className="evidence__meta">
                {matchedLabel(hit)}
                {hit.entry_id ? (
                  <>
                    {" · "}
                    <a href={`#entry-${hit.entry_id}`}>Show in your entries</a>
                  </>
                ) : null}
              </p>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
