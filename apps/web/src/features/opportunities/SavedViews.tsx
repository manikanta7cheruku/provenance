import { useState } from "react";
import { ApiError } from "../../lib/api";
import { deleteView, fetchViews, saveView, storedToQuery } from "../../lib/workbench-api";
import type { Query, SavedView } from "../../lib/workbench-api";
import { useAsync } from "../../lib/useAsync";
import { ActionButton, ConfirmDialog, Notice, Select, TextField } from "../../ui";

/** Saved views: a name for a view and its filters. Choosing one applies it. */
export function SavedViews({ query, onApply }: { query: Query; onApply: (query: Query) => void }) {
  const views = useAsync((signal) => fetchViews(signal), []);
  const [chosen, setChosen] = useState("");
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<SavedView | null>(null);

  const list = views.data ?? [];
  const current = list.find((v) => v.id === chosen) ?? null;

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const made = await saveView(name, query);
      setSaving(false);
      setName("");
      setChosen(made.id);
      views.reload();
    } catch (caught) {
      setError(caught instanceof ApiError ? (caught.fields.name ?? caught.message) : "The view could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(view: SavedView) {
    setBusy(true);
    try {
      await deleteView(view.id);
      setChosen("");
      setConfirmDelete(null);
      views.reload();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The view could not be deleted.");
      setConfirmDelete(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bench__views">
      {views.error ? (
        <Notice tone="warn">
          <p>Saved views could not be loaded. Your list still works.</p>
        </Notice>
      ) : (
        <Select
          label="Saved views"
          value={chosen}
          onChange={(event) => {
            const id = event.target.value;
            setChosen(id);
            const view = list.find((v) => v.id === id);
            if (view) onApply(storedToQuery(view.query));
          }}
        >
          <option value="">{list.length === 0 ? "None saved yet" : "Choose a view"}</option>
          {list.map((view) => (
            <option key={view.id} value={view.id}>
              {view.name}
            </option>
          ))}
        </Select>
      )}
      <div className="bench__viewactions">
        {saving ? (
          <form
            className="bench__saveview"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <TextField label="Name this view" value={name} error={error ?? undefined} onChange={(event) => setName(event.target.value)} />
            <ActionButton type="submit" variant="primary" disabled={busy || !name.trim()}>
              Save view
            </ActionButton>
            <ActionButton
              onClick={() => {
                setSaving(false);
                setError(null);
              }}
            >
              Cancel
            </ActionButton>
          </form>
        ) : (
          <ActionButton onClick={() => setSaving(true)}>Save this view</ActionButton>
        )}
        {current ? <ActionButton onClick={() => setConfirmDelete(current)}>Delete this view</ActionButton> : null}
      </div>
      {error && !saving ? (
        <Notice tone="warn">
          <p>{error}</p>
        </Notice>
      ) : null}
      <ConfirmDialog
        open={confirmDelete !== null}
        title="Delete this saved view?"
        confirmLabel="Delete view"
        danger
        busy={busy}
        onCancel={() => setConfirmDelete(null)}
        onConfirm={() => confirmDelete && void remove(confirmDelete)}
      >
        <p>
          The view {confirmDelete ? `"${confirmDelete.name}"` : ""} is removed. Your jobs are not changed.
        </p>
      </ConfirmDialog>
    </div>
  );
}
