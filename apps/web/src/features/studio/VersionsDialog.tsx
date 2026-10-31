import { useEffect, useState } from "react";
import { fetchVersions, restoreVersion } from "../../lib/studio-api";
import type { ResumeDocument, VersionInfo } from "../../lib/studio-api";
import { formatDateTime } from "../../lib/format";
import { ApiError } from "../../lib/api";
import { ActionButton, Dialog, Notice, Skeleton } from "../../ui";

interface VersionsDialogProps {
  open: boolean;
  resumeId: string;
  /** The revision after pending edits are saved. */
  getRevision: () => number;
  onClose: () => void;
  onRestored: (doc: ResumeDocument) => void;
  /** Saves pending edits first, so the version being left is kept. */
  beforeRestore: () => Promise<void>;
}

export function VersionsDialog({ open, resumeId, getRevision, onClose, onRestored, beforeRestore }: VersionsDialogProps) {
  const [versions, setVersions] = useState<VersionInfo[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setVersions(null);
    setProblem(null);
    const controller = new AbortController();
    fetchVersions(resumeId, controller.signal)
      .then(setVersions)
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setProblem(caught instanceof ApiError ? caught.message : "The history could not be loaded.");
        }
      });
    return () => controller.abort();
  }, [open, resumeId]);

  async function restore(id: string) {
    setBusy(id);
    setProblem(null);
    try {
      await beforeRestore();
      onRestored(await restoreVersion(resumeId, id, getRevision()));
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "That version could not be restored. Nothing was changed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Dialog
      open={open}
      title="Earlier versions"
      onClose={onClose}
      actions={
        <ActionButton autoFocus onClick={onClose}>
          Close
        </ActionButton>
      }
    >
      <p>
        A version is kept every couple of minutes while you edit. Restoring one keeps what you have now as
        another version, so you can go back.
      </p>
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}
      {versions === null && !problem ? <Skeleton label="Loading versions" lines={3} /> : null}
      {versions !== null && versions.length === 0 ? <p>No earlier versions yet. They appear as you edit.</p> : null}
      {versions && versions.length > 0 ? (
        <ol className="versions">
          {versions.map((v) => (
            <li key={v.id}>
              <span>
                Version {v.revision}, saved {formatDateTime(v.created_at)}
              </span>
              <ActionButton onClick={() => void restore(v.id)} disabled={busy !== null}>
                {busy === v.id ? "Restoring" : `Restore version ${v.revision}`}
              </ActionButton>
            </li>
          ))}
        </ol>
      ) : null}
    </Dialog>
  );
}
