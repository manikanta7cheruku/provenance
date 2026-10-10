import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { resetPassword } from "../../lib/auth-api";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, TextField } from "../../ui";
import { AuthFrame } from "./AuthFrame";

export function ResetPasswordPage() {
  useDocumentTitle("Choose a new password");
  const [params] = useSearchParams();
  const token = params.get("token");
  const form = useFormSubmit();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <AuthFrame title="Choose a new password">
        <Notice tone="danger" title="This link is incomplete.">
          Open the link from your email again, or request a new one.
        </Notice>
        <p className="auth__links">
          <Link to="/forgot-password">Request a new link</Link>
        </p>
      </AuthFrame>
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!password) errors.new_password = "Choose a new password.";
    else if (password !== confirm) errors.confirm = "The two passwords do not match.";
    await form.submit(errors, async () => {
      await resetPassword(token ?? "", password);
      setDone(true);
    });
  }

  if (done) {
    return (
      <AuthFrame title="Password updated">
        <Notice tone="info" title="Your password was changed.">
          Every device was signed out. Sign in with your new password.
        </Notice>
        <p className="auth__links">
          <Link to="/signin">Go to sign in</Link>
        </p>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame title="Choose a new password">
      <form ref={form.formRef} onSubmit={onSubmit} noValidate>
        {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
        <TextField
          label="New password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters."
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={form.fieldErrors.new_password}
        />
        <TextField
          label="Confirm new password"
          name="confirm"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          error={form.fieldErrors.confirm}
        />
        <div className="auth__actions">
          <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
            Change password
          </Button>
        </div>
      </form>
    </AuthFrame>
  );
}
