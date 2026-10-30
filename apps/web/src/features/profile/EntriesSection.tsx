import { useState } from "react";
import {
  createEntry,
  deleteEntry,
  fetchEntries,
  fetchEntrySpecs,
  updateEntry,
} from "../../lib/profile-api";
import type { EntryData, EntrySpec, ProfileEntry } from "../../lib/profile-api";
import { useAsync } from "../../lib/useAsync";
import { ActionButton, ConfirmDialog, EmptyState, Notice, Section, Skeleton } from "../../ui";
import { flagLabels, provenanceLabel, summarize } from "./describe";
import { EntryForm } from "./EntryForm";

interface EntriesSectionProps {
  /** Changes when the resume was read again, so the list reloads. */
  version: number;
  onChanged: () => void;
}

export function EntriesSection({ version, onChanged }: EntriesSectionProps) {
  const specs = useAsync((signal) => fetchEntrySpecs(signal), []);
  const entries = useAsync((signal) => fetchEntries(signal), [version]);
  const [adding, setAdding] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [removing, setRemoving] = useState<ProfileEntry | null>(null);
  const [removeBusy, setRemoveBusy] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const error = specs.error ?? entries.error;
  if (error) {
    return (
      <Section title="Your entries">
        <Notice tone="danger" title="Your entries could not be loaded">
          <p>{error.message} Nothing was changed.</p>
          <p>
            <ActionButton
              onClick={() => {
                specs.reload();
                entries.reload();
              }}
            >
              Try again
            </ActionButton>
          </p>
        </Notice>
      </Section>
    );
  }
  if (!specs.data || !entries.data) {
    return (
      <Section title="Your entries">
        <Skeleton label="Loading your entries" lines={5} />
      </Section>
    );
  }

  const allSpecs = specs.data;
  const list = entries.data;
  const specFor = (type: string): EntrySpec | undefined => allSpecs.find((s) => s.entry_type === type);

  async function save(spec: EntrySpec, entry: ProfileEntry | null, data: EntryData) {
    if (entry) await updateEntry(entry.id, data);
    else await createEntry(spec.entry_type, data);
    setAdding(null);
    setEditing(null);
    entries.reload();
    onChanged();
  }

  async function confirmRemove() {
    if (!removing) return;
    setRemoveBusy(true);
    setRemoveError(null);
    try {
      await deleteEntry(removing.id);
      setRemoving(null);
      entries.reload();
      onChanged();
    } catch (caught) {
      setRemoveError(caught instanceof Error ? caught.message : "Could not remove this entry.");
    } finally {
      setRemoveBusy(false);
    }
  }

  const needsCorrection = list.filter((entry) => entry.flags.length > 0).length;

  return (
    <Section title="Your entries">
      <p className="entries__lead">
        This is the evidence every job is compared against. Each entry says where it came from.
        Edit anything that is wrong, and add what your resume leaves out.
      </p>

      {needsCorrection > 0 ? (
        <Notice tone="warn">
          <p>
            {needsCorrection} {needsCorrection === 1 ? "entry is" : "entries are"} missing details that
            make your matches more accurate. They are marked below.
          </p>
        </Notice>
      ) : null}

      {list.length === 0 && adding === null ? (
        <EmptyState
          title="Your profile has no entries yet"
          why="Matches are only as good as the evidence behind them. Without entries there is nothing to compare a job against."
          next="Upload your resume above, or add your first entry by hand below."
        />
      ) : null}

      {allSpecs.map((spec) => {
        const group = list.filter((entry) => entry.entry_type === spec.entry_type);
        if (group.length === 0 && adding !== spec.entry_type) return null;
        return (
          <div key={spec.entry_type} className="entries__group">
            <h3 className="entries__heading">
              {spec.plural} <span className="entries__count">{group.length}</span>
            </h3>
            <ul className="entries__list">
              {group.map((entry) => {
                const info = summarize(entry, spec);
                const flags = flagLabels(entry, spec);
                const isEditing = editing === entry.id;
                return (
                  <li
                    key={entry.id}
                    id={`entry-${entry.id}`}
                    className="entry"
                    data-flagged={flags.length > 0 || undefined}
                  >
                    <div className="entry__head">
                      <div className="entry__main">
                        <p className="entry__title">{info.title}</p>
                        {info.subtitle ? <p className="entry__subtitle">{info.subtitle}</p> : null}
                        {info.detail ? <p className="entry__detail">{info.detail}</p> : null}
                        <p className="entry__meta">
                          {provenanceLabel(entry)}
                          {flags.length > 0 ? ` · Missing: ${flags.join(", ")}` : ""}
                        </p>
                      </div>
                      {isEditing ? null : (
                        <div className="entry__actions">
                          <ActionButton
                            onClick={() => {
                              setAdding(null);
                              setEditing(entry.id);
                            }}
                            aria-label={`Edit ${info.title}`}
                          >
                            Edit
                          </ActionButton>
                          <ActionButton
                            onClick={() => {
                              setRemoveError(null);
                              setRemoving(entry);
                            }}
                            aria-label={`Remove ${info.title}`}
                          >
                            Remove
                          </ActionButton>
                        </div>
                      )}
                    </div>
                    {isEditing ? (
                      <EntryForm
                        spec={spec}
                        initial={entry.data}
                        onSave={(data) => save(spec, entry, data)}
                        onCancel={() => setEditing(null)}
                      />
                    ) : null}
                  </li>
                );
              })}
              {adding === spec.entry_type ? (
                <li className="entry">
                  <p className="entry__title">New {spec.label.toLowerCase()}</p>
                  <EntryForm
                    spec={spec}
                    initial={null}
                    onSave={(data) => save(spec, null, data)}
                    onCancel={() => setAdding(null)}
                  />
                </li>
              ) : null}
            </ul>
          </div>
        );
      })}

      <div className="entries__add" role="group" aria-label="Add an entry">
        <span className="entries__add-label">Add</span>
        {allSpecs.map((spec) => (
          <ActionButton
            key={spec.entry_type}
            onClick={() => {
              setEditing(null);
              setAdding(spec.entry_type);
            }}
          >
            {spec.label}
          </ActionButton>
        ))}
      </div>

      <ConfirmDialog
        open={removing !== null}
        title="Remove this entry?"
        confirmLabel="Remove entry"
        danger
        busy={removeBusy}
        onCancel={() => setRemoving(null)}
        onConfirm={() => void confirmRemove()}
      >
        <p>
          {removing ? `"${summarize(removing, specFor(removing.entry_type)).title}" ` : ""}
          is removed from your profile. Your resume file is not affected, and reading it again would
          bring a parsed entry back.
        </p>
        {removeError ? <p role="alert">{removeError}</p> : null}
      </ConfirmDialog>
    </Section>
  );
}
