import { useState } from "react";
import type { FormEvent } from "react";
import { createInvite, fetchInvites, revokeInvite } from "../../lib/admin-api";
import type { Invite } from "../../lib/admin-api";
import { formatDateTime } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, ConfirmDialog, DataTable } from "../../ui";

const STATUS_LABEL: Record<Invite["status"], string> = {
  active: "Active",
  used: "Used",
  revoked: "Revoked",
  expired: "Expired",
};

export function InvitesPage() {
  const heading = usePageChrome("Invites");
  const { data, error, loading, reload } = useAsync((signal) => fetchInvites(signal), []);
  const [email, setEmail] = useState("");
  const [days, setDays] = useState(7);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<{ code: string; email: string | null } | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [revoking, setRevoking] = useState<Invite | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setMessage(null);
    try {
      const result = await createInvite(email, days);
      setCreated({ code: result.code, email: result.invite.email });
      setEmail("");
      reload();
    } catch (caught) {
      setCreated(null);
      setMessage({ ok: false, text: caught instanceof Error ? caught.message : "Something went wrong." });
    } finally {
      setCreating(false);
    }
  }

  async function copy() {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.code);
      setMessage({ ok: true, text: "Copied to the clipboard." });
    } catch {
      setMessage({ ok: false, text: "Could not copy. Select the code and copy it yourself." });
    }
  }

  async function confirmRevoke() {
    if (!revoking) return;
    setBusy(true);
    try {
      const result = await revokeInvite(revoking.id);
      setMessage({ ok: true, text: result.message });
    } catch (caught) {
      setMessage({ ok: false, text: caught instanceof Error ? caught.message : "Something went wrong." });
    } finally {
      setBusy(false);
      setRevoking(null);
      reload();
    }
  }

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        Invites
      </h1>
      <p>Sign-up is invite only. Each code works once. Only a hash of the code is stored.</p>

      <form className="admin__filters" onSubmit={(e) => void submit(e)} aria-label="Create an invite">
        <label className="admin__field">
          Limit to one email (optional)
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} autoComplete="off" />
        </label>
        <label className="admin__field">
          Valid for (days)
          <input type="number" min={1} max={30} value={days} onChange={(e) => setDays(Math.min(30, Math.max(1, Number(e.target.value) || 1)))} />
        </label>
        <ActionButton variant="primary" type="submit" disabled={creating}>
          {creating ? "Creating\u2026" : "Create invite"}
        </ActionButton>
      </form>

      <div role="status">
        {created && (
          <div className="admin__message">
            <p>
              Copy this code now. It is shown once and cannot be shown again
              {created.email ? ` (valid only for ${created.email})` : ""}.
            </p>
            <p className="admin__code">{created.code}</p>
            <ActionButton onClick={() => void copy()}>Copy code</ActionButton>{" "}
            <ActionButton onClick={() => setCreated(null)}>I have copied it</ActionButton>
          </div>
        )}
        {message && <p className={message.ok ? "admin__message" : "admin__message admin__message--error"}>{message.text}</p>}
      </div>

      {loading && <p>Loading invites{"\u2026"}</p>}
      {error && (
        <div role="alert" className="admin__message">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}
      {data && data.length === 0 && <p>No invites yet.</p>}
      {data && data.length > 0 && (
        <DataTable caption="Invites (newest first)">
          <thead>
            <tr>
              <th scope="col">For</th>
              <th scope="col">Status</th>
              <th scope="col">Created</th>
              <th scope="col">Expires</th>
              <th scope="col">Created by</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {data.map((invite) => (
              <tr key={invite.id}>
                <td>{invite.email ?? "Anyone"}</td>
                <td>{STATUS_LABEL[invite.status]}</td>
                <td>{formatDateTime(invite.created_at)}</td>
                <td>{formatDateTime(invite.expires_at)}</td>
                <td>{invite.created_by_email ?? "Operator command"}</td>
                <td>
                  {invite.status === "active" ? (
                    <ActionButton variant="danger" onClick={() => setRevoking(invite)}>
                      Revoke
                    </ActionButton>
                  ) : (
                    "None"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}

      <ConfirmDialog
        open={revoking !== null}
        title="Revoke this invite?"
        confirmLabel="Revoke invite"
        danger
        busy={busy}
        onConfirm={() => void confirmRevoke()}
        onCancel={() => setRevoking(null)}
      >
        <p>The code stops working immediately. This is recorded in the audit log.</p>
      </ConfirmDialog>
    </>
  );
}
