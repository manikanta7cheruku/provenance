import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { finishGitHub } from "../../lib/github-api";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { Notice, PageHeader, Skeleton } from "../../ui";

/**
 * Where GitHub sends the person back. The code and the state in the address are used once and then
 * removed from it, so they do not stay in the browser history. If GitHub says the person declined,
 * or anything is off, the screen says so in one sentence and offers the way back.
 */
export function GitHubCallbackPage() {
  useDocumentTitle("Connecting GitHub");
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [problem, setProblem] = useState<string | null>(null);
  // React runs effects twice in development. The code can be used once, so the call is made once.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const code = params.get("code");
    const state = params.get("state");
    const denied = params.get("error");
    // Take the secrets out of the address bar and the history before anything else happens.
    window.history.replaceState(null, "", "/connect/github/callback");
    if (denied) {
      setProblem(
        denied === "access_denied"
          ? "You chose not to connect GitHub, so nothing was connected. You can try again whenever you like."
          : "GitHub did not complete the sign-in. Nothing was connected. Try again from your profile.",
      );
      return;
    }
    if (!code || !state) {
      setProblem("This page is only for the return from GitHub. Start from Connect GitHub on your profile.");
      return;
    }
    finishGitHub(code, state)
      .then(() => navigate("/profile", { replace: true }))
      .catch((caught: unknown) => {
        setProblem(caught instanceof ApiError ? caught.message : "GitHub could not be connected. Nothing was changed. Try again from your profile.");
      });
  }, [params, navigate]);

  return (
    <>
      <PageHeader title="Connecting GitHub" />
      {problem ? (
        <Notice tone="warn" title="GitHub was not connected">
          <p>{problem}</p>
          <p>
            <Link to="/profile">Back to your profile</Link>
          </p>
        </Notice>
      ) : (
        <Skeleton label="Connecting GitHub" lines={2} />
      )}
    </>
  );
}
