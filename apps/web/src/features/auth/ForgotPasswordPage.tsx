import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../../lib/auth-api";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, TextField } from "../../ui";
import { AuthFrame } from "./AuthFrame";

export function ForgotPasswordPage() {
  useDocumentTitle("Reset your password");
  const form = useFormSubmit();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!email.trim()) errors.email = "Enter the email address for your account.";
    await form.submit(errors, async () => {
      await forgotPassword(email.trim());
      setSent(true);
    });
  }

  return (
    <AuthFrame
      title="Reset your password"
      description="Enter your email address and we will send you a link to choose a new password."
    >
      {sent ? (
        <>
          <Notice tone="info" title="Check your inbox.">
            If an account exists for that address, we sent a link. It works once and expires in 1
            hour.
          </Notice>
          <p className="auth__links">
            <Link to="/signin">Back to sign in</Link>
          </p>
        </>
      ) : (
        <>
          <form ref={form.formRef} onSubmit={onSubmit} noValidate>
            {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
            <TextField
              label="Email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              error={form.fieldErrors.email}
            />
            <div className="auth__actions">
              <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
                Send reset link
              </Button>
            </div>
          </form>
          <p className="auth__links">
            <Link to="/signin">Back to sign in</Link>
          </p>
        </>
      )}
    </AuthFrame>
  );
}
