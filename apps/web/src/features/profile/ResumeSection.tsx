import { useEffect, useRef, useState } from "react";
import {
  confirmResume,
  deleteResume,
  fetchResume,
  reparseResume,
  RESUME_DOWNLOAD_URL,
  RESUME_EXTENSIONS,
  RESUME_MAX_BYTES,
  uploadResume,
} from "../../lib/resume-api";
import type { Resume } from "../../lib/resume-api";
import { formatDateTime } from "../../lib/format";
import { describeResumeState, isResumeBusy } from "../../lib/states";
import type { ResumeUiState } from "../../lib/states";
import { useAsync } from "../../lib/useAsync";
import { ApiError } from "../../lib/api";
import {
  ActionButton,
  ConfirmDialog,
  FileDrop,
  formatBytes,
  Notice,
  Section,
  Skeleton,
  Status,
} from "../../ui";

const POLL_MS = 2000;

interface ResumeSectionProps {
  /** Called when the entries may have changed (a parse finished, the resume was removed). */
  onChanged: () => void;
}

export function ResumeSection({ onChanged }: ResumeSectionProps) {
  const { data: resume, error, loading, reload } = useAsync((signal) => fetchResume(signal), []);
  const [uploading, setUploading] = useState<{ name: string; size: number } | null>(null);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const previous = useRef<ResumeUiState | null>(null);

  const state = resume?.ui_state ?? null;

  // While the resume is being read, keep asking. Stops by itself when it settles.
  useEffect(() => {
    if (state === null || !isResumeBusy(state)) return;
    const timer = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(timer);
  }, [state, reload]);

  // When reading finishes, the entries below have new content.
  useEffect(() => {
    if (previous.current !== null && isResumeBusy(previous.current) && state && !isResumeBusy(state)) {
      onChanged();
    }
    previous.current = state;
  }, [state, onChanged]);

  async function run(action: () => Promise<unknown>, after?: () => void) {
    setBusy(true);
    setProblem(undefined);
    try {
      await action();
      after?.();
      reload();
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "Something unexpected happened. Your data is safe. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function onSelect(file: File) {
    setProblem(undefined);
    setUploading({ name: file.name, size: file.size });
    try {
      await uploadResume(file);
      reload();
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "Something unexpected happened. Nothing was saved. Try again.");
    } finally {
      setUploading(null);
    }
  }

  if (error) {
    return (
      <Section title="Your resume">
        <Notice tone="danger" title="Your resume could not be loaded">
          <p>{error.message} Nothing was changed.</p>
          <p>
            <ActionButton onClick={reload}>Try again</ActionButton>
          </p>
        </Notice>
      </Section>
    );
  }
  if (loading) {
    return (
      <Section title="Your resume">
        <Skeleton label="Loading your resume" lines={3} />
      </Section>
    );
  }

  return (
    <Section title="Your resume">
      {uploading ? (
        <p role="status" className="resume__uploading">
          <Status tone="neutral" label={`Uploading ${uploading.name} (${formatBytes(uploading.size)})`} />
        </p>
      ) : resume ? (
        <ResumeDetails
          resume={resume}
          busy={busy}
          onConfirm={() => void run(confirmResume)}
          onReread={() => void run(reparseResume, onChanged)}
          onDelete={() => setConfirmDelete(true)}
        />
      ) : (
        <>
          <p className="resume__lead">
            Upload your resume and we will turn it into entries you can check and correct. Your file
            stays private: only you can download it, and you can delete it at any time.
          </p>
          <div className="form-narrow">
            <FileDrop
              label="Resume"
              hint={`PDF or DOCX, up to ${formatBytes(RESUME_MAX_BYTES)}. Text only: a scanned picture cannot be read.`}
              extensions={RESUME_EXTENSIONS}
              maxBytes={RESUME_MAX_BYTES}
              file={null}
              error={problem}
              onSelect={(file) => void onSelect(file)}
              onReject={setProblem}
            />
          </div>
          <p className="resume__alt">No resume yet? Add your entries by hand below.</p>
        </>
      )}

      {resume && problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete your resume file?"
        confirmLabel="Delete resume"
        danger
        busy={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() =>
          void run(deleteResume, () => {
            setConfirmDelete(false);
            onChanged();
          })
        }
      >
        <p>
          The file and its stored copy are removed. The entries in your profile stay, so your
          matches are not affected. You can upload a new resume afterwards.
        </p>
      </ConfirmDialog>
    </Section>
  );
}

function ResumeDetails({
  resume,
  busy,
  onConfirm,
  onReread,
  onDelete,
}: {
  resume: Resume;
  busy: boolean;
  onConfirm: () => void;
  onReread: () => void;
  onDelete: () => void;
}) {
  const info = describeResumeState(resume.ui_state);
  const canConfirm = resume.ui_state === "parsed" || resume.ui_state === "needs_correction";
  return (
    <div className="resume">
      <p className="resume__file">
        <span className="resume__name">{resume.original_filename}</span>
        <span className="resume__facts">
          {resume.file_kind.toUpperCase()}
          {` · ${formatBytes(resume.size_bytes)}`}
          {resume.page_count ? ` · ${resume.page_count} ${resume.page_count === 1 ? "page" : "pages"}` : ""}
        </span>
      </p>

      <p role="status" className="resume__state">
        <Status tone={info.tone} label={info.label} />
        <span className="resume__explanation">{info.explanation}</span>
      </p>

      {resume.ui_state === "failed" ? (
        <Notice tone="danger" title="This resume could not be turned into a profile">
          <p>{resume.error_message}</p>
          <p>
            You can add your entries by hand below, read the same file again
            {resume.can_retry ? "" : " (a different file will work better)"}, or delete it and upload
            another.
          </p>
        </Notice>
      ) : null}

      {resume.parsed_at && resume.ui_state !== "failed" ? (
        <p className="resume__summary">
          {resume.kept_entry_count} {resume.kept_entry_count === 1 ? "entry" : "entries"} found in your resume.
          {resume.dropped_entry_count > 0
            ? ` ${resume.dropped_entry_count} suggested ${resume.dropped_entry_count === 1 ? "item was" : "items were"} not in your resume text, so ${resume.dropped_entry_count === 1 ? "it was" : "they were"} left out.`
            : ""}
          {resume.confirmed_at ? ` You confirmed this on ${formatDateTime(resume.confirmed_at)}.` : ""}
        </p>
      ) : null}

      <div className="resume__actions">
        {canConfirm ? (
          <ActionButton variant="primary" onClick={onConfirm} disabled={busy}>
            {resume.ui_state === "needs_correction" ? "Confirm anyway" : "Confirm my profile"}
          </ActionButton>
        ) : null}
        <a className="action" href={RESUME_DOWNLOAD_URL}>
          Download my file
        </a>
        {resume.can_retry ? (
          <ActionButton onClick={onReread} disabled={busy}>
            Read it again
          </ActionButton>
        ) : null}
        <ActionButton onClick={onDelete} disabled={busy}>
          Delete resume
        </ActionButton>
      </div>
      {resume.can_retry && resume.ui_state !== "failed" ? (
        <p className="resume__hint">
          Reading it again replaces entries that came from the resume and that you have not edited.
          Your edits and the entries you added are kept.
        </p>
      ) : null}
    </div>
  );
}
