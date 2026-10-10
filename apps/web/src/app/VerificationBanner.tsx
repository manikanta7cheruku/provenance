import { useState } from "react";
import { requestVerification } from "../lib/auth-api";
import { useSession } from "../lib/session";
import { useFormSubmit } from "../lib/useFormSubmit";
import { Button, Notice } from "../ui";

/** Shown only when this deployment requires a confirmed email and the user has not confirmed. */
export function VerificationBanner() {
  const session = useSession();
  const form = useFormSubmit();
  const [sent, setSent] = useState(false);
  if (session.state.kind !== "authenticated") return null;
  const { user, config } = session.state;
  if (!config.email_verification_required || user.email_verified) return null;

  async function onResend() {
    await form.submit({}, async () => {
      await requestVerification();
      setSent(true);
    });
  }

  return (
    <div className="banner">
      <Notice tone="warn" title="Confirm your email to keep editing.">
        <p>
          {sent
            ? `We sent a new link to ${user.email}.`
            : `We sent a confirmation link to ${user.email}. You can look around, but changes are paused until you confirm.`}
        </p>
        {form.notice ? <p>{form.notice.text}</p> : null}
        {sent ? null : (
          <Button busy={form.busy} disabled={form.blocked} onClick={() => void onResend()}>
            Send the link again
          </Button>
        )}
      </Notice>
    </div>
  );
}
