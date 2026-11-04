import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { enterJob } from "../../lib/imports-api";
import { POSTING_MAX_CHARS, POSTING_MIN_CHARS, SOURCE_NAMES } from "../../lib/jobs-api";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, Select, TextArea, TextField } from "../../ui";

/** Type a job in field by field. It is saved and read exactly like a pasted posting. */
export function ManualJobForm({ onAdded }: { onAdded: () => void }) {
  const navigate = useNavigate();
  const form = useFormSubmit();
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [source, setSource] = useState<string>(SOURCE_NAMES[0]);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!title.trim()) errors.title = "Enter the job title.";
    if (description.trim().length + title.trim().length < POSTING_MIN_CHARS) {
      errors.description = `Add more of the description. The title, company and description together need at least ${POSTING_MIN_CHARS} characters.`;
    } else if (description.length > POSTING_MAX_CHARS) {
      errors.description = `This is over ${POSTING_MAX_CHARS.toLocaleString()} characters. Keep the description only.`;
    }
    await form.submit(errors, async () => {
      const result = await enterJob({
        title: title.trim(),
        company: company.trim(),
        location: location.trim(),
        source_name: source,
        source_url: url.trim() || null,
        description,
      });
      onAdded();
      navigate(`/opportunities/${result.job.id}`, { state: { duplicate: result.duplicate } });
    });
  }

  return (
    <form ref={form.formRef} className="jobs__form" onSubmit={onSubmit} noValidate>
      {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
      <TextField
        label="Job title"
        value={title}
        error={form.fieldErrors.title}
        onChange={(event) => setTitle(event.target.value)}
      />
      <TextField
        label="Company (optional)"
        value={company}
        error={form.fieldErrors.company}
        onChange={(event) => setCompany(event.target.value)}
      />
      <TextField
        label="Place (optional)"
        hint="For example Pune, India, or Remote."
        value={location}
        error={form.fieldErrors.location}
        onChange={(event) => setLocation(event.target.value)}
      />
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
        label="What the job asks for"
        hint="Write or copy what you know: the duties, the requirements, the place. We only read what you give us."
        rows={9}
        value={description}
        error={form.fieldErrors.description}
        onChange={(event) => setDescription(event.target.value)}
      />
      <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
        Read this job
      </Button>
    </form>
  );
}
