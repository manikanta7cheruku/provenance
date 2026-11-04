import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { IMPORT_EXTENSIONS, IMPORT_MAX_BYTES, IMPORT_MAX_ROWS, startFileImport } from "../../lib/imports-api";
import { SOURCE_NAMES } from "../../lib/jobs-api";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, FileDrop, Notice, Select } from "../../ui";

/** Upload a spreadsheet of jobs. Each row is checked and the report says what happened to every one. */
export function ImportFileForm({ onStarted }: { onStarted: () => void }) {
  const navigate = useNavigate();
  const form = useFormSubmit();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | undefined>();
  const [source, setSource] = useState<string>("Other");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!file) errors.file = "Choose a CSV or Excel file first.";
    await form.submit(errors, async () => {
      if (!file) return;
      const batch = await startFileImport(file, source);
      setFile(null);
      onStarted();
      navigate(`/opportunities/imports/${batch.id}`);
    });
  }

  return (
    <form ref={form.formRef} className="jobs__form" onSubmit={onSubmit} noValidate>
      <p className="jobs__lead">
        Bring a list of jobs from a spreadsheet. The first row names the columns. One column must hold the job
        description, called Description, Job description, Details, Posting or Text. Title, Company, Location, Link and
        Source columns are used when present. Up to {IMPORT_MAX_ROWS} jobs per file. Formulas are never calculated.
      </p>
      {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
      <FileDrop
        label="Spreadsheet"
        hint="A CSV or Excel (.xlsx) file, up to 5 MB. Macros and password protection are not accepted."
        extensions={IMPORT_EXTENSIONS}
        maxBytes={IMPORT_MAX_BYTES}
        file={file}
        error={fileError ?? form.fieldErrors.file}
        onSelect={(chosen) => {
          setFile(chosen);
          setFileError(undefined);
        }}
        onReject={(message) => {
          setFile(null);
          setFileError(message);
        }}
        disabled={form.busy}
      />
      <Select
        label="Where did these jobs come from?"
        hint="Used for rows that do not have a Source column. It is only a label for your own list."
        value={source}
        onChange={(event) => setSource(event.target.value)}
      >
        {SOURCE_NAMES.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </Select>
      <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
        Import these jobs
      </Button>
    </form>
  );
}
