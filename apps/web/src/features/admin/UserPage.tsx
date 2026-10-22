import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { fetchUser, runUserAction } from "../../lib/admin-api";
import type { UserAction } from "../../lib/admin-api";
import { formatDateTime, formatNumber } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, ConfirmDialog, DataTable, Status } from "../../ui";

interface Pending {
  action: UserAction;
  title: string;
  body: string;
  confirm: string;
  danger: boolean;
}

export function UserPage() {
  const { userId = "" } = useParams();
  const { data, error, loading, reload } = useAsync((signal) => fetchUser(userId, signal), [userId]);
  const heading = usePageChrome(data ? data.user.email : "User");
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  if (error instanceof ApiError && error.status === 404) {
    return (
      <>
        <h1 ref={heading} tabIndex={-1}>
          User not found
        </h1>
        <Link to="/admin/users">Back to users</Link>
      </>
    );
  }

  async function confirm() {
    if (!pending) return;
    setBusy(true);
    try {
      const result = await runUserAction(userId, pending.action);
      setMessage({ ok: true, text: result.message });
    } catch (caught) {
      // The server explains guard failures ("only active administrator", "cannot disable yourself").
      setMessage({ ok: false, text: caught instanceof Error ? caught.message : "Something went wrong." });
    } finally {
      setBusy(false);
      setPending(null);
      reload();
    }
  }

  const user = data?.user;
  const choices: Pending[] = user
    ? [
        user.is_active
          ? {
              action: "disable",
              title: "Disable this account?",
              body: "The person is signed out everywhere and cannot sign in until you enable the account again. Their data is kept.",
              confirm: "Disable account",
              danger: true,
            }
          : {
              action: "enable",
              title: "Enable this account?",
              body: "The person can sign in again.",
              confirm: "Enable account",
              danger: false,
            },
        {
          action: "revoke-sessions",
          title: "End all sessions?",
          body: "The person is signed out on every device and must sign in again.",
          confirm: "End sessions",
          danger: true,
        },
        user.role === "ADMIN"
          ? {
              action: "demote",
              title: "Remove administrator role?",
              body: "The account becomes a regular user. The last active administrator cannot be demoted.",
              confirm: "Remove role",
              danger: true,
            }
          : {
              action: "promote",
              title: "Make this person an administrator?",
              body: "Administrators can manage accounts, invites and the queue. They still cannot read anyone's resume, profile or jobs.",
              confirm: "Make administrator",
              danger: false,
            },
        ...(user.email_verified
          ? []
          : [
              {
                action: "resend-verification" as const,
                title: "Send a new confirmation email?",
                body: "An email with a new confirmation link is queued. Older links stop working.",
                confirm: "Send email",
                danger: false,
              },
            ]),
        ...(user.is_active
          ? [
              {
                action: "send-password-reset" as const,
                title: "Send a password reset email?",
                body: "An email with a one-hour reset link is queued for the account's own address. Your own session and the person's password are not changed.",
                confirm: "Send email",
                danger: false,
              },
            ]
          : []),
      ]
    : [];

  return (
    <>
      <p>
        <Link to="/admin/users">Back to users</Link>
      </p>
      <h1 ref={heading} tabIndex={-1}>
        {user ? user.email : "User"}
      </h1>

      <div role="status">
        {message && <p className={message.ok ? "admin__message" : "admin__message admin__message--error"}>{message.text}</p>}
      </div>
      {loading && <p>Loading{"\u2026"}</p>}
      {error && (
        <div role="alert" className="admin__message">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}

      {user && data && (
        <>
          <dl className="admin__counts">
            <div>
              <dt>Account</dt>
              <dd>
                <Status tone={user.is_active ? "ok" : "danger"} label={user.is_active ? "Active" : "Disabled"} />
              </dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>{user.role === "ADMIN" ? "Administrator" : "User"}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{user.email_verified ? "Confirmed" : "Not confirmed"}</dd>
            </div>
            <div>
              <dt>Active sessions</dt>
              <dd>{formatNumber(user.active_sessions)}</dd>
            </div>
            <div>
              <dt>Profile entries</dt>
              <dd>{formatNumber(user.profile_entries_count)}</dd>
            </div>
            <div>
              <dt>Runs</dt>
              <dd>{formatNumber(user.runs_count)}</dd>
            </div>
          </dl>
          <p className="admin__muted">
            Created {formatDateTime(user.created_at)}. Last seen {formatDateTime(user.last_seen_at)}. Counters
            only: you cannot see this person's resume, profile or jobs.
          </p>

          <h2>Actions</h2>
          <div className="admin__actions">
            {choices.map((choice) => (
              <ActionButton
                key={choice.action}
                variant={choice.danger ? "danger" : "quiet"}
                onClick={() => setPending(choice)}
              >
                {choice.confirm}
              </ActionButton>
            ))}
          </div>

          <h2>Recent audit events</h2>
          {data.recent_events.length === 0 ? (
            <p>No events yet.</p>
          ) : (
            <DataTable caption="Recent events about or by this account">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Action</th>
                  <th scope="col">By</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_events.map((event) => (
                  <tr key={event.id}>
                    <td>{formatDateTime(event.created_at)}</td>
                    <td>{event.action}</td>
                    <td>{event.actor_email ?? "System"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </>
      )}

      <ConfirmDialog
        open={pending !== null}
        title={pending?.title ?? ""}
        confirmLabel={pending?.confirm ?? "Confirm"}
        danger={pending?.danger ?? false}
        busy={busy}
        onConfirm={() => void confirm()}
        onCancel={() => setPending(null)}
      >
        <p>{pending?.body}</p>
        <p>
          Account: <strong>{user?.email}</strong>. This action is recorded in the audit log.
        </p>
      </ConfirmDialog>
    </>
  );
}
