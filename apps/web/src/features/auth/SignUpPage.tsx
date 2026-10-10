import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useSession } from "../../lib/session";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, TextField } from "../../ui";
import { AuthFrame } from "./AuthFrame";
import { SessionUnavailable } from "./SessionUnavailable";

export function SignUpPage() {
  useDocumentTitle("Create account");
  const session = useSession();
  const navigate = useNavigate();
  const form = useFormSubmit();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");

  if (session.state.kind === "authenticated") return <Navigate to="/opportunities" replace />;
  if (session.state.kind === "loading") {
    return (
      <AuthFrame title="Create your account">
        <p role="status">Checking your session...</p>
      </AuthFrame>
    );
  }
  if (session.state.kind === "error") {
    return (
      <AuthFrame title="Create your account">
        <SessionUnavailable message={session.state.message} />
      </AuthFrame>
    );
  }
  const inviteOnly = session.state.config.signup_mode === "invite";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!email.trim()) errors.email = "Enter your email address.";
    if (!password) errors.password = "Choose a password.";
    if (inviteOnly && !inviteCode.trim()) errors.invite_code = "Enter the invite code you were given.";
    await form.submit(errors, async () => {
      await session.signUp(email.trim(), password, inviteOnly ? inviteCode.trim() : null);
      navigate("/opportunities", { replace: true });
    });
  }

  return (
    <AuthFrame
      title="Create your account"
      description={
        inviteOnly
          ? "Provenance is invite-only for now. Use the code you were given."
          : "Create an account to start analyzing jobs against your real experience."
      }
    >
      <form ref={form.formRef} onSubmit={onSubmit} noValidate>
        {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
        {inviteOnly ? (
          <TextField
            label="Invite code"
            name="invite_code"
            autoComplete="off"
            value={inviteCode}
            onChange={(event) => setInviteCode(event.target.value)}
            error={form.fieldErrors.invite_code}
          />
        ) : null}
        <TextField
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={form.fieldErrors.email}
        />
        <TextField
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters. A long phrase works well."
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={form.fieldErrors.password}
        />
        <div className="auth__actions">
          <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
            Create account
          </Button>
        </div>
      </form>
      <p className="auth__links">
        Already have an account? <Link to="/signin">Sign in</Link>
      </p>
    </AuthFrame>
  );
}
