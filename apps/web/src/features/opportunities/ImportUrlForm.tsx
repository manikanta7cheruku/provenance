import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { startUrlImport } from "../../lib/imports-api";
import { SOURCE_NAMES } from "../../lib/jobs-api";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, Select, TextField } from "../../ui";

/** Ask us to read one web page. The page is read by our server, never by this browser. */
export function ImportUrlForm({ onStarted }: { onStarted: () => void }) {
  const navigate = useNavigate();
  const form = useFormSubmit();
  const [url, setUrl] = useState("");
  const [source, setSource] = useState<string>("Company career page");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!url.trim()) errors.url = "Enter the address of the job posting.";
    else if (!/^https:\/\//i.test(url.trim())) errors.url = "Enter an address that starts with https://.";
    await form.submit(errors, async () => {
      const batch = await startUrlImport(url.trim(), source);
      setUrl("");
      onStarted();
      navigate(`/opportunities/imports/${batch.id}`);
    });
  }

  return (
    <form ref={form.formRef} className="jobs__form" onSubmit={onSubmit} noValidate>
      <p className="jobs__lead">
        Give us the address of one job posting and we read that page for you. Pages that ask you to sign in cannot be
        read. Some sites, such as LinkedIn and Indeed, do not allow automated reading: copy the description and paste it
        instead.
      </p>
      {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
      <TextField
        label="Web address of the posting"
        hint="It must start with https://. We read this one page and nothing else on the site."
        type="url"
        inputMode="url"
        autoComplete="off"
        value={url}
        error={form.fieldErrors.url}
        onChange={(event) => setUrl(event.target.value)}
      />
      <Select
        label="What kind of site is it?"
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
      <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
        Read this page
      </Button>
    </form>
  );
}
