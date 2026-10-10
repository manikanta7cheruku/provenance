import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useSession } from "../../lib/session";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, TextField } from "../../ui";
import { AuthFrame } from "./AuthFrame";
import { nextPath } from "./nextPath";
import { SessionUnavailable } from "./SessionUnavailable";

export function SignInPage() {
  useDocumentTitle("Sign in");
  const session = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const form = useFormSubmit();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const destination = nextPath(location.state);

  if (session.state.kind === "authenticated") return <Navigate to={destination} replace />;
  if (session.state.kind === "loading") {
    return (
      <AuthFrame title="Sign in">
        <p role="status">Checking your session...</p>
      </AuthFrame>
    );
  }
  if (session.state.kind === "error") {
    return (
      <AuthFrame title="Sign in">
        <SessionUnavailable message={session.state.message} />
      </AuthFrame>
    );
  }
  const expired = session.state.expired;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!email.trim()) errors.email = "Enter your email address.";
    if (!password) errors.password = "Enter your password.";
    await form.submit(errors, async () => {
      await session.signIn(email.trim(), password);
      navigate(destination, { replace: true });
    });
  }

  return (
    <AuthFrame title="Sign in" description="Welcome back. Sign in to continue.">
      <form ref={form.formRef} onSubmit={onSubmit} noValidate>
        {expired ? (
          <Notice tone="info" title="Your session ended.">
            Sign in again to continue where you left off.
          </Notice>
        ) : null}
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
        <TextField
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={form.fieldErrors.password}
        />
        <div className="auth__actions">
          <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
            Sign in
          </Button>
        </div>
      </form>
      <p className="auth__links">
        <Link to="/forgot-password">Forgot your password?</Link>
      </p>
      <p className="auth__links">
        New here? <Link to="/signup">Create an account</Link>
      </p>
    </AuthFrame>
  );
}
