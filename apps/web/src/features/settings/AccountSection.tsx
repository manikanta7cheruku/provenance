import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { changePassword, requestVerification } from "../../lib/auth-api";
import { useSession } from "../../lib/session";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { Button, Notice, Section, Status, TextField } from "../../ui";

export function AccountSection() {
  const session = useSession();
  const navigate = useNavigate();
  const verifyForm = useFormSubmit();
  const passwordForm = useFormSubmit();
  const [verificationSent, setVerificationSent] = useState(false);
  const [passwordChanged, setPasswordChanged] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  if (session.state.kind !== "authenticated") return null;
  const { user } = session.state;

  async function onResend() {
    await verifyForm.submit({}, async () => {
      await requestVerification();
      setVerificationSent(true);
    });
  }

  async function onChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordChanged(false);
    const errors: Record<string, string> = {};
    if (!current) errors.current_password = "Enter your current password.";
    if (!next) errors.new_password = "Choose a new password.";
    else if (next !== confirm) errors.confirm = "The two passwords do not match.";
    await passwordForm.submit(errors, async () => {
      session.adopt(await changePassword(current, next));
      setCurrent("");
      setNext("");
      setConfirm("");
      setPasswordChanged(true);
    });
  }

  async function onSignOut() {
    await session.signOut();
    navigate("/signin", { replace: true });
  }

  return (
    <>
      <Section title="Account">
        <table className="data-table">
          <caption className="visually-hidden">Account</caption>
          <tbody>
            <tr>
              <th scope="row">Email</th>
              <td>{user.email}</td>
            </tr>
            <tr>
              <th scope="row">Email status</th>
              <td>
                {user.email_verified ? (
                  <Status tone="ok" label="Confirmed" />
                ) : (
                  <Status tone="warn" label="Not confirmed" />
                )}
              </td>
            </tr>
          </tbody>
        </table>
        {!user.email_verified ? (
          <div className="actions">
            {verifyForm.notice ? (
              <Notice tone={verifyForm.notice.tone}>{verifyForm.notice.text}</Notice>
            ) : null}
            {verificationSent ? (
              <Notice tone="info">We sent a confirmation link to {user.email}.</Notice>
            ) : (
              <Button busy={verifyForm.busy} disabled={verifyForm.blocked} onClick={() => void onResend()}>
                Send confirmation link
              </Button>
            )}
          </div>
        ) : null}
        <p className="actions">
          <Button onClick={() => void onSignOut()}>Sign out</Button>
        </p>
      </Section>

      <Section title="Password">
        <form ref={passwordForm.formRef} onSubmit={onChangePassword} noValidate className="form-narrow">
          {passwordForm.notice ? (
            <Notice tone={passwordForm.notice.tone}>{passwordForm.notice.text}</Notice>
          ) : null}
          {passwordChanged ? (
            <Notice tone="info" title="Password changed.">
              Your other devices were signed out.
            </Notice>
          ) : null}
          <TextField
            label="Current password"
            name="current_password"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            error={passwordForm.fieldErrors.current_password}
          />
          <TextField
            label="New password"
            name="new_password"
            type="password"
            autoComplete="new-password"
            hint="At least 12 characters."
            value={next}
            onChange={(event) => setNext(event.target.value)}
            error={passwordForm.fieldErrors.new_password}
          />
          <TextField
            label="Confirm new password"
            name="confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            error={passwordForm.fieldErrors.confirm}
          />
          <div className="actions">
            <Button type="submit" variant="primary" busy={passwordForm.busy} disabled={passwordForm.blocked}>
              Change password
            </Button>
          </div>
        </form>
      </Section>
    </>
  );
}
