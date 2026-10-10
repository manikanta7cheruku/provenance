import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { confirmEmail } from "../../lib/auth-api";
import { useSession } from "../../lib/session";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { Notice } from "../../ui";
import { AuthFrame } from "./AuthFrame";

type State = { kind: "working" } | { kind: "done" } | { kind: "failed"; message: string };

export function VerifyEmailPage() {
  useDocumentTitle("Confirm your email");
  const [params] = useSearchParams();
  const token = params.get("token");
  const session = useSession();
  const [state, setState] = useState<State>(
    token ? { kind: "working" } : { kind: "failed", message: "This link is incomplete." },
  );
  // The token works once. React StrictMode runs effects twice in development, so guard it.
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    confirmEmail(token)
      .then(() => {
        setState({ kind: "done" });
        void session.refresh();
      })
      .catch((error: unknown) => {
        setState({
          kind: "failed",
          message: error instanceof ApiError ? error.message : "Something went wrong. Try again.",
        });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <AuthFrame title="Confirm your email">
      {state.kind === "working" ? <p role="status">Confirming your email address...</p> : null}
      {state.kind === "done" ? (
        <>
          <Notice tone="info" title="Your email address is confirmed.">
            You can use every feature now.
          </Notice>
          <p className="auth__links">
            <Link to="/opportunities">Continue</Link>
          </p>
        </>
      ) : null}
      {state.kind === "failed" ? (
        <>
          <Notice tone="danger" title="We could not confirm your email.">
            {state.message}
          </Notice>
          <p className="auth__links">
            Sign in and request a new link from <Link to="/settings">Settings</Link>.
          </p>
        </>
      ) : null}
    </AuthFrame>
  );
}
