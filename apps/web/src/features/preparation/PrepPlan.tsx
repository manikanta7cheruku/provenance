import { useEffect, useState } from "react";
import {
  PLAN_KIND_WORDS,
  saveCompany,
  setInterviewDate,
} from "../../lib/preparation-api";
import { ActionButton, Notice, Section, TextArea, TextField } from "../../ui";
import type { PrepProps } from "./PrepOverview";

function formatDay(day: string): string {
  return new Date(`${day}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function PrepPlan({ jobId, data, onUpdate, onProblem }: PrepProps) {
  const [date, setDate] = useState(data.interview_date ?? "");
  const [link, setLink] = useState(data.company_info.link);
  const [notes, setNotes] = useState(data.company_info.notes);
  const [dateError, setDateError] = useState<string | undefined>();
  const [linkError, setLinkError] = useState<string | undefined>();
  const [saved, setSaved] = useState("");
  const company = data.company_info;

  useEffect(() => setDate(data.interview_date ?? ""), [data.interview_date]);

  async function saveDate() {
    setDateError(undefined);
    try {
      onUpdate(await setInterviewDate(jobId, date || null));
      setSaved(date ? "Plan updated." : "Date cleared.");
    } catch (caught) {
      setDateError(
        caught instanceof Error
          ? caught.message
          : "That date could not be saved.",
      );
      onProblem(caught, "That date could not be saved.");
    }
  }

  async function saveNotes() {
    setLinkError(undefined);
    try {
      onUpdate(await saveCompany(jobId, link, notes));
      setSaved("Company notes saved.");
    } catch (caught) {
      const fields = (caught as { fields?: Record<string, string> }).fields;
      if (fields?.link) setLinkError(fields.link);
      else onProblem(caught, "Your notes could not be saved.");
    }
  }

  return (
    <>
      <Section title="Your plan">
        <p className="field__hint">
          Give the day of the interview and get a day by day plan. Critical gaps
          come first, and the last two days are for review and a mock interview.
        </p>
        <div className="prep__form">
          <TextField
            label="Interview date"
            type="date"
            min={today()}
            value={date}
            error={dateError}
            onChange={(event) => setDate(event.target.value)}
          />
          <ActionButton variant="primary" onClick={() => void saveDate()}>
            Make the plan
          </ActionButton>
        </div>
        <p className="visually-hidden" role="status">
          {saved}
        </p>
        {data.plan.length === 0 ? (
          <p className="job__note">
            No plan yet. Choose the interview date above.
          </p>
        ) : (
          <ol className="prep__plan" aria-label="Day by day plan">
            {data.plan.map((day) => (
              <li key={day.date}>
                <strong>{formatDay(day.date)}</strong>
                <span className="prep__plankind">
                  {PLAN_KIND_WORDS[day.kind] ?? day.kind}
                </span>
                {day.topics.length > 0 ? (
                  <span>{day.topics.join("; ")}</span>
                ) : (
                  <span className="field__hint">
                    Take a mock interview from the Mock interview tab.
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </Section>
      <Section title="The company">
        <p className="field__hint">
          What the posting itself says about the company is shown here. Nothing
          is looked up on the web for you. Add what you find yourself and keep
          it with the job.
        </p>
        <dl className="prep__facts">
          <dt>Company</dt>
          <dd>{company.name || "Not stated in the posting"}</dd>
          <dt>Where the posting came from</dt>
          <dd>
            {company.source_name}
            {company.source_url ? (
              <>
                {" "}
                <a
                  href={company.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  Open the original posting
                </a>
              </>
            ) : null}
          </dd>
          {company.says.map((line) => (
            <div key={line} className="prep__fact">
              <dt>From the posting</dt>
              <dd>{line}</dd>
            </div>
          ))}
        </dl>
        <TextField
          label="Company page you found (optional)"
          hint="Kept so you can open it later. It is never fetched."
          value={link}
          error={linkError}
          onChange={(event) => setLink(event.target.value)}
        />
        <TextArea
          label="Your notes about the company"
          hint="What it does, who its customers are, anything you want to mention. Only you see this."
          value={notes}
          maxLength={4000}
          onChange={(event) => setNotes(event.target.value)}
        />
        <ActionButton onClick={() => void saveNotes()}>
          Save company notes
        </ActionButton>
        {link && !linkError ? (
          <p className="field__hint">
            <a href={link} target="_blank" rel="noreferrer noopener">
              Open the company page
            </a>
          </p>
        ) : null}
        <Notice tone="info">
          <p>
            Nothing about the company here is invented. If you want a summary,
            add notes from the company&apos;s own pages and they stay with this
            job.
          </p>
        </Notice>
      </Section>
    </>
  );
}
