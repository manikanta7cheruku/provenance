import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { pasteJob, POSTING_MAX_CHARS, POSTING_MIN_CHARS, SOURCE_NAMES } from "../../lib/jobs-api";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, Section, Select, TextArea, TextField } from "../../ui";

/** Paste a posting. The text is stored as you pasted it. We never visit a link you give us. */
export function PasteJobForm({ onPasted }: { onPasted: () => void }) {
  const navigate = useNavigate();
  const form = useFormSubmit();
  const [source, setSource] = useState<string>(SOURCE_NAMES[0]);
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (text.trim().length < POSTING_MIN_CHARS) {
      errors.text = "This looks too short to be a job posting. Paste the whole description.";
    } else if (text.length > POSTING_MAX_CHARS + 2000) {
      errors.text = `This is over ${POSTING_MAX_CHARS.toLocaleString()} characters. Paste the description only.`;
    }
    await form.submit(errors, async () => {
      const result = await pasteJob({ source_name: source, source_url: url.trim() || null, text });
      setText("");
      setUrl("");
      onPasted();
      navigate(`/opportunities/${result.job.id}`, { state: { duplicate: result.duplicate } });
    });
  }

  return (
    <Section title="Paste a job">
      <p className="jobs__lead">
        Copy a job description from anywhere and paste it here. We read what it asks for and tell
        you whether anything stands in your way. The text stays private to you. We never visit the
        site you copied it from.
      </p>
      <form ref={form.formRef} className="jobs__form" onSubmit={onSubmit} noValidate>
        {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
        <Select
          label="Where did you find it?"
          hint="This is only a label for your own list."
          value={source}
          error={form.fieldErrors.source_name}
          onChange={(event) => setSource(event.target.value)}
        >
          {SOURCE_NAMES.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </Select>
        <TextField
          label="Link to the posting (optional)"
          hint="Kept so you can open it later. We never request it."
          type="url"
          value={url}
          error={form.fieldErrors.source_url}
          onChange={(event) => setUrl(event.target.value)}
        />
        <TextArea
          label="Job description"
          hint={`Paste the whole posting: the title, the company and what it asks for. ${POSTING_MIN_CHARS} to ${POSTING_MAX_CHARS.toLocaleString()} characters.`}
          rows={10}
          value={text}
          error={form.fieldErrors.text}
          onChange={(event) => setText(event.target.value)}
        />
        <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
          Read this job
        </Button>
      </form>
    </Section>
  );
}
