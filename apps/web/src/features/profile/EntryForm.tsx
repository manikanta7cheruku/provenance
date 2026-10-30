import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import type { EntryData, EntrySpec, FieldSpec } from "../../lib/profile-api";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, TextArea, TextField } from "../../ui";

interface EntryFormProps {
  spec: EntrySpec;
  initial: EntryData | null;
  onSave: (data: EntryData) => Promise<void>;
  onCancel: () => void;
}

function toText(value: unknown): string {
  if (Array.isArray(value)) return value.join("\n");
  return typeof value === "string" ? value : "";
}

/** Form values are strings. Lists are one item per line. Empty values are left out. */
function toData(spec: EntrySpec, values: Record<string, string>): EntryData {
  const data: EntryData = {};
  for (const field of spec.fields) {
    const raw = values[field.name]?.trim() ?? "";
    if (!raw) continue;
    data[field.name] = field.kind === "list" ? raw.split("\n").map((line) => line.trim()).filter(Boolean) : raw;
  }
  return data;
}

function Field({
  field,
  value,
  error,
  onChange,
}: {
  field: FieldSpec;
  value: string;
  error: string | undefined;
  onChange: (value: string) => void;
}) {
  const label = field.required ? field.label : `${field.label} (optional)`;
  const hint = field.hint || undefined;
  if (field.kind === "longtext" || field.kind === "list") {
    return (
      <TextArea
        label={label}
        {...(hint ? { hint } : {})}
        error={error}
        rows={field.kind === "list" ? 4 : 3}
        value={value}
        maxLength={field.kind === "list" ? 4000 : field.max_length}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }
  return (
    <TextField
      label={label}
      {...(hint ? { hint } : {})}
      error={error}
      type={field.kind === "url" ? "url" : "text"}
      value={value}
      maxLength={field.max_length}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

/** One form for every entry type: the fields come from the server's spec. Escape cancels. */
export function EntryForm({ spec, initial, onSave, onCancel }: EntryFormProps) {
  const form = useFormSubmit();
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(spec.fields.map((f) => [f.name, toText(initial?.[f.name])])),
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    for (const field of spec.fields) {
      if (field.required && !values[field.name]?.trim()) errors[field.name] = "This is required.";
    }
    await form.submit(errors, () => onSave(toData(spec, values)));
  }

  function onKeyDown(event: KeyboardEvent<HTMLFormElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onCancel();
    }
  }

  return (
    <form ref={form.formRef} className="entry-form" onSubmit={onSubmit} onKeyDown={onKeyDown} noValidate>
      {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
      {spec.fields.map((field) => (
        <Field
          key={field.name}
          field={field}
          value={values[field.name] ?? ""}
          error={form.fieldErrors[field.name]}
          onChange={(value) => setValues((previous) => ({ ...previous, [field.name]: value }))}
        />
      ))}
      <div className="entry-form__actions">
        <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
          Save
        </Button>
        <Button onClick={onCancel} disabled={form.busy}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
