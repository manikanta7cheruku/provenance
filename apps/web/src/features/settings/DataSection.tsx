import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  DELETE_PHRASE,
  EXPORT_PATH,
  deleteAccount,
} from "../../lib/account-api";
import { ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import {
  ActionButton,
  ConfirmDialog,
  Notice,
  Section,
  TextField,
} from "../../ui";

/** Your data: take a copy of it, or delete the account. Deleting is final. */
export function DataSection() {
  const session = useSession();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [phrase, setPhrase] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function close() {
    if (busy) return;
    setOpen(false);
    setPassword("");
    setPhrase("");
    setErrors({});
    setFailure(null);
  }

  async function confirm() {
    const found: Record<string, string> = {};
    if (!password) found.password = "Enter your password.";
    if (phrase.trim().toLowerCase().replace(/\s+/g, " ") !== DELETE_PHRASE)
      found.confirm = `Type "${DELETE_PHRASE}" to confirm.`;
    setErrors(found);
    setFailure(null);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    try {
      await deleteAccount(password, phrase);
      await session.refresh();
      navigate("/signin", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && Object.keys(caught.fields).length > 0)
        setErrors(caught.fields);
      else
        setFailure(
          caught instanceof ApiError
            ? caught.message
            : "The account could not be deleted. Try again.",
        );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Your data">
      <p>
        Take a copy of what you put into Provenance, or delete your account. See
        the <Link to="/privacy">privacy policy</Link> for what is kept and for
        how long.
      </p>
      <h3>Download a copy</h3>
      <p className="field__hint">
        Your preferences, profile entries, resumes made in the studio, jobs with
        your decisions and notes, drafts and saved views, as one file. It leaves
        out your password, sign-in sessions and the files you uploaded.
      </p>
      <p>
        <a
          className="button"
          href={EXPORT_PATH}
          download="Provenance data.json"
        >
          Download my data
        </a>
      </p>
      <h3>Delete my account</h3>
      <p>
        This removes your profile, resumes, jobs, drafts and everything else you
        added, and signs you out everywhere. It cannot be undone. Copies in
        backups are kept for a limited time (see the privacy policy). Download a
        copy first if you want one.
      </p>
      <p>
        <ActionButton variant="danger" onClick={() => setOpen(true)}>
          Delete my account
        </ActionButton>
      </p>
      <ConfirmDialog
        open={open}
        title="Delete your account?"
        confirmLabel="Delete my account"
        danger
        busy={busy}
        onConfirm={() => void confirm()}
        onCancel={close}
      >
        <form
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            void confirm();
          }}
          noValidate
        >
          <p>Everything you added is deleted and you cannot get it back.</p>
          {failure ? <Notice tone="danger">{failure}</Notice> : null}
          <TextField
            label="Your password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={errors.password}
          />
          <TextField
            label={`Type "${DELETE_PHRASE}"`}
            autoComplete="off"
            value={phrase}
            onChange={(event) => setPhrase(event.target.value)}
            error={errors.confirm}
          />
        </form>
      </ConfirmDialog>
    </Section>
  );
}
