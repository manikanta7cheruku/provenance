import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { fetchUsers } from "../../lib/admin-api";
import type { UserFilters } from "../../lib/admin-api";
import { formatDateTime, formatNumber } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable, Status } from "../../ui";

const EMPTY: UserFilters = { q: "", role: "", status: "", verified: "" };

export function UsersPage() {
  const heading = usePageChrome("Users");
  const [draft, setDraft] = useState<UserFilters>(EMPTY);
  const [applied, setApplied] = useState<UserFilters>(EMPTY);
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useAsync(
    (signal) => fetchUsers(applied, offset, signal),
    [applied, offset],
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setApplied(draft);
  }

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        Users
      </h1>
      <form className="admin__filters" onSubmit={submit} role="search" aria-label="Filter users">
        <label className="admin__field">
          Email contains
          <input value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} maxLength={100} />
        </label>
        <label className="admin__field">
          Role
          <select value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value as UserFilters["role"] })}>
            <option value="">Any</option>
            <option value="USER">User</option>
            <option value="ADMIN">Administrator</option>
          </select>
        </label>
        <label className="admin__field">
          Account
          <select value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value as UserFilters["status"] })}>
            <option value="">Any</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
          </select>
        </label>
        <label className="admin__field">
          Email
          <select value={draft.verified} onChange={(e) => setDraft({ ...draft, verified: e.target.value as UserFilters["verified"] })}>
            <option value="">Any</option>
            <option value="true">Confirmed</option>
            <option value="false">Not confirmed</option>
          </select>
        </label>
        <ActionButton variant="primary" type="submit">
          Apply filters
        </ActionButton>
      </form>

      {loading && <p>Loading users{"\u2026"}</p>}
      {error && (
        <div role="alert" className="admin__message">
          <p>{error.message}</p>
          <ActionButton onClick={reload}>Try again</ActionButton>
        </div>
      )}
      {data && data.items.length === 0 && <p>No users match these filters.</p>}
      {data && data.items.length > 0 && (
        <>
          <DataTable caption={`Users (${data.total})`}>
            <thead>
              <tr>
                <th scope="col">Email</th>
                <th scope="col">Role</th>
                <th scope="col">Account</th>
                <th scope="col">Email confirmed</th>
                <th scope="col">Last seen</th>
                <th scope="col" className="num">Sessions</th>
                <th scope="col" className="num">Entries</th>
                <th scope="col" className="num">Runs</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((user) => (
                <tr key={user.id}>
                  <td>
                    <Link to={`/admin/users/${user.id}`}>{user.email}</Link>
                  </td>
                  <td>{user.role === "ADMIN" ? "Administrator" : "User"}</td>
                  <td>
                    <Status tone={user.is_active ? "ok" : "danger"} label={user.is_active ? "Active" : "Disabled"} />
                  </td>
                  <td>{user.email_verified ? "Yes" : "No"}</td>
                  <td>{formatDateTime(user.last_seen_at)}</td>
                  <td className="num">{formatNumber(user.active_sessions)}</td>
                  <td className="num">{formatNumber(user.profile_entries_count)}</td>
                  <td className="num">{formatNumber(user.runs_count)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
          <div className="admin__pager">
            <ActionButton disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - data.limit))}>
              Previous
            </ActionButton>
            <span>
              {offset + 1} to {Math.min(offset + data.limit, data.total)} of {data.total}
            </span>
            <ActionButton disabled={offset + data.limit >= data.total} onClick={() => setOffset(offset + data.limit)}>
              Next
            </ActionButton>
          </div>
        </>
      )}
    </>
  );
}
