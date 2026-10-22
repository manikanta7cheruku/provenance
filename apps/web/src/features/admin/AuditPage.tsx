import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { fetchAudit } from "../../lib/admin-api";
import type { AuditEvent } from "../../lib/admin-api";
import { formatDateTime } from "../../lib/format";
import { usePageChrome } from "../../lib/usePageChrome";
import { ActionButton, DataTable } from "../../ui";

type Filters = { category: "" | "audit" | "security"; action: string };
const EMPTY: Filters = { category: "", action: "" };

export function AuditPage() {
  const heading = usePageChrome("Audit log");
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorText, setErrorText] = useState("");

  const load = useCallback(
    async (before: string | null, append: boolean) => {
      setStatus("loading");
      try {
        const page = await fetchAudit(applied, before);
        setItems((previous) => (append ? [...previous, ...page.items] : page.items));
        setNext(page.next_before);
        setStatus("ready");
      } catch (caught) {
        setErrorText(caught instanceof Error ? caught.message : "Something went wrong.");
        setStatus("error");
      }
    },
    [applied],
  );

  useEffect(() => {
    void load(null, false);
  }, [load]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setApplied(draft);
  }

  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        Audit log
      </h1>
      <p>
        Append-only record of security events and administrator actions. It never contains passwords,
        tokens, plain email addresses of failed sign-ins, or user content.
      </p>
      <form className="admin__filters" onSubmit={submit} role="search" aria-label="Filter audit events">
        <label className="admin__field">
          Category
          <select value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value as Filters["category"] })}>
            <option value="">All</option>
            <option value="audit">Audit</option>
            <option value="security">Security</option>
          </select>
        </label>
        <label className="admin__field">
          Action starts with
          <input value={draft.action} onChange={(e) => setDraft({ ...draft, action: e.target.value })} placeholder="admin." maxLength={100} />
        </label>
        <ActionButton variant="primary" type="submit">
          Apply filters
        </ActionButton>
      </form>

      {status === "error" && (
        <div role="alert" className="admin__message">
          <p>{errorText}</p>
          <ActionButton onClick={() => void load(null, false)}>Try again</ActionButton>
        </div>
      )}
      {status === "loading" && items.length === 0 && <p>Loading events{"\u2026"}</p>}
      {status === "ready" && items.length === 0 && <p>No events match these filters.</p>}
      {items.length > 0 && (
        <>
          <DataTable caption="Events (newest first)">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Category</th>
                <th scope="col">Action</th>
                <th scope="col">By</th>
                <th scope="col">Target</th>
              </tr>
            </thead>
            <tbody>
              {items.map((event) => (
                <tr key={event.id}>
                  <td>{formatDateTime(event.created_at)}</td>
                  <td>{event.category}</td>
                  <td>{event.action}</td>
                  <td>{event.actor_email ?? "System"}</td>
                  <td>{event.target_type ? `${event.target_type} ${event.target_id ?? ""}` : "None"}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
          {next && (
            <ActionButton disabled={status === "loading"} onClick={() => void load(next, true)}>
              {status === "loading" ? "Loading\u2026" : "Older events"}
            </ActionButton>
          )}
        </>
      )}
    </>
  );
}
