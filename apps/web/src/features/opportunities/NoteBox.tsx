import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import { saveNote } from "../../lib/workbench-api";
import type { Decision } from "../../lib/workbench-api";
import { Button, TextArea } from "../../ui";

const MAX = 2000;

/** A private note on one job. Saved only when the person presses Save. */
export function NoteBox({ jobId, note, onSaved }: { jobId: string; note: string; onSaved: (decision: Decision) => void }) {
  const [value, setValue] = useState(note);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  // A different job starts with an empty message and its own note. A note that changed elsewhere
  // replaces the text, and the message about the last save stays.
  useEffect(() => setMessage(null), [jobId]);
  useEffect(() => setValue(note), [jobId, note]);

  const changed = value.trim() !== note.trim();

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const decision = await saveNote(jobId, value);
      onSaved(decision);
      setMessage({ tone: "ok", text: "Note saved." });
    } catch (caught) {
      setMessage({ tone: "error", text: caught instanceof ApiError ? (caught.fields.note ?? caught.message) : "The note could not be saved." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="notebox">
      <TextArea
        label="Your note"
        hint="Private to you. For a contact, a deadline or why you are unsure."
        rows={4}
        maxLength={MAX + 200}
        value={value}
        error={value.length > MAX ? `A note can be up to ${MAX.toLocaleString()} characters.` : message?.tone === "error" ? message.text : undefined}
        onChange={(event) => setValue(event.target.value)}
      />
      <p className="notebox__row">
        <Button variant="secondary" busy={busy} disabled={!changed || value.length > MAX} onClick={() => void save()}>
          Save note
        </Button>
        <span role="status" className="notebox__status">
          {message?.tone === "ok" ? message.text : ""}
        </span>
      </p>
    </div>
  );
}
