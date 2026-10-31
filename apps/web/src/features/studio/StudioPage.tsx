import { useCallback, useState } from "react";
import { ApiError } from "../../lib/api";
import { createResume, deleteResume, fetchOptions, fetchResume, fetchResumes } from "../../lib/studio-api";
import type { ResumeDocument, StudioOptions } from "../../lib/studio-api";
import { useAsync } from "../../lib/useAsync";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { ActionButton, ConfirmDialog, Notice, PageHeader, Section, SegmentedControl, Skeleton, Status } from "../../ui";
import { ContentEditor } from "./ContentEditor";
import { ExportPanel } from "./ExportPanel";
import { saveText } from "./labels";
import { Preview } from "./Preview";
import { StylePanel, TemplateChoice } from "./StylePanel";
import { useStudioDocument, usePreview } from "./useStudioDocument";
import { VersionsDialog } from "./VersionsDialog";
import "./studio.css";

type StartKind = "profile" | "blank";

function StartScreen({ options, onCreated }: { options: StudioOptions; onCreated: (doc: ResumeDocument) => void }) {
  const [template, setTemplate] = useState("classic");
  const [start, setStart] = useState<StartKind>("profile");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function create() {
    setBusy(true);
    setProblem(null);
    try {
      onCreated(await createResume({ start, template }));
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "The resume could not be started. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Resume studio"
        description="Build a resume you control: your words, your layout, and a PDF that matches what you see."
      />
      <Section title="Start your resume">
        <p className="studio__lead">
          A first draft can be built from your profile. It uses only what you already entered there, and you
          can change every word. Your free plan keeps {options.max_resumes} {options.max_resumes === 1 ? "resume" : "resumes"}.
        </p>
        <div className="studio__start">
          <SegmentedControl<StartKind>
            legend="Start from"
            showLegend
            value={start}
            onChange={setStart}
            options={[
              { value: "profile", label: "My profile" },
              { value: "blank", label: "A blank page" },
            ]}
          />
          <TemplateChoice options={options} value={template} onChange={setTemplate} name="start-template" />
          {problem ? (
            <Notice tone="danger">
              <p>{problem}</p>
            </Notice>
          ) : null}
          <ActionButton variant="primary" onClick={() => void create()} disabled={busy}>
            {busy ? "Starting" : "Start my resume"}
          </ActionButton>
        </div>
      </Section>
    </>
  );
}

type Tab = "content" | "style";
type Pane = "edit" | "preview";

function Editor({
  initial,
  options,
  onDeleted,
}: {
  initial: ResumeDocument;
  options: StudioOptions;
  onDeleted: () => void;
}) {
  const doc = useStudioDocument(initial);
  const preview = usePreview(initial.id, doc.content);
  const [tab, setTab] = useState<Tab>("content");
  const [pane, setPane] = useState<Pane>("edit");
  const [epoch, setEpoch] = useState(0);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  useDocumentTitle("Resume studio");

  const announce = useCallback((text: string) => setMessage(text), []);

  async function reload() {
    doc.replace(await fetchResume(initial.id));
    setEpoch((n) => n + 1);
  }

  async function remove() {
    setBusy(true);
    try {
      await deleteResume(initial.id);
      onDeleted();
    } catch {
      setProblem("The resume could not be deleted. Nothing was changed.");
      setBusy(false);
      setDeleting(false);
    }
  }

  const problems = Object.entries(doc.problems);
  return (
    <>
      <PageHeader title="Resume studio" description="Edit on the left. The page on the right is what the PDF will look like." />

      <div className="studio__bar">
        <p role="status" className="studio__save">
          <Status
            tone={doc.state === "saved" ? "ok" : doc.state === "error" || doc.state === "conflict" ? "danger" : "neutral"}
            label={saveText(doc.state, doc.savedAt)}
          />
        </p>
        <div className="studio__actions">
          <ActionButton onClick={() => setHistory(true)}>Earlier versions</ActionButton>
          <ActionButton onClick={() => setDeleting(true)}>Delete this resume</ActionButton>
        </div>
      </div>

      {doc.state === "conflict" ? (
        <Notice tone="warn" title="This resume was changed somewhere else">
          <p>Your latest edits are not saved. Load the newer version to keep working. Your unsaved edits here will be replaced.</p>
          <p>
            <ActionButton onClick={() => void reload()}>Load the newer version</ActionButton>
          </p>
        </Notice>
      ) : null}
      {doc.state === "error" && problems.length > 0 ? (
        <Notice tone="danger" title="Some details need fixing before this can be saved">
          <ul>
            {problems.slice(0, 4).map(([path, text]) => (
              <li key={path}>{text}</li>
            ))}
          </ul>
        </Notice>
      ) : null}
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}

      <div className="studio__panes">
        <SegmentedControl<Pane>
          legend="Show"
          value={pane}
          onChange={setPane}
          options={[
            { value: "edit", label: "Edit" },
            { value: "preview", label: "Preview" },
          ]}
        />
      </div>

      <div className={`studio studio--${pane}`}>
        <section className="studio__edit" aria-label="Editor">
          <SegmentedControl<Tab>
            legend="Editing"
            value={tab}
            onChange={setTab}
            options={[
              { value: "content", label: "Content" },
              { value: "style", label: "Design" },
            ]}
          />
          {tab === "content" ? (
            <ContentEditor doc={doc.content} onChange={doc.setContent} problems={doc.problems} epoch={epoch} announce={announce} />
          ) : (
            <StylePanel doc={doc.content} options={options} onChange={doc.setContent} problems={doc.problems} />
          )}
          <Section title="PDF">
            <ExportPanel resumeId={initial.id} beforeExport={doc.flush} fileName={doc.content.header.name} />
          </Section>
        </section>
        <section className="studio__view" aria-label="Preview">
          <Preview html={preview.html} paper={doc.content.style.paper} failed={preview.failed} />
        </section>
      </div>

      <p className="visually-hidden" role="status" aria-live="polite">
        {message}
      </p>

      <VersionsDialog
        open={history}
        resumeId={initial.id}
        getRevision={doc.getRevision}
        onClose={() => setHistory(false)}
        beforeRestore={doc.flush}
        onRestored={(restored) => {
          doc.replace(restored);
          setEpoch((n) => n + 1);
          setHistory(false);
          announce("Earlier version restored.");
        }}
      />
      <ConfirmDialog
        open={deleting}
        title="Delete this resume?"
        confirmLabel="Delete resume"
        danger
        busy={busy}
        onCancel={() => setDeleting(false)}
        onConfirm={() => void remove()}
      >
        <p>The resume, its earlier versions and any PDFs made from it are deleted. Your profile entries are not affected.</p>
      </ConfirmDialog>
    </>
  );
}

export function StudioPage() {
  useDocumentTitle("Resume studio");
  const options = useAsync((signal) => fetchOptions(signal), []);
  const list = useAsync((signal) => fetchResumes(signal), []);
  const first = list.data?.[0]?.id;
  const loaded = useAsync(
    async (signal) => (first ? fetchResume(first, signal) : null),
    [first],
  );
  const [created, setCreated] = useState<ResumeDocument | null>(null);
  const [deletedId, setDeletedId] = useState<string | null>(null);

  const error = options.error ?? list.error ?? loaded.error;
  if (error) {
    return (
      <>
        <PageHeader title="Resume studio" />
        <Notice tone="danger" title="The studio could not be loaded">
          <p>{error.message} Nothing was changed.</p>
          <p>
            <ActionButton
              onClick={() => {
                options.reload();
                list.reload();
                loaded.reload();
              }}
            >
              Try again
            </ActionButton>
          </p>
        </Notice>
      </>
    );
  }
  if (!options.data || !list.data || (first && !loaded.data && !created)) {
    return (
      <>
        <PageHeader title="Resume studio" />
        <Skeleton label="Loading the studio" lines={5} />
      </>
    );
  }
  const current = created ?? (loaded.data && loaded.data.id !== deletedId ? loaded.data : null);
  if (!current) {
    return <StartScreen options={options.data} onCreated={setCreated} />;
  }
  return (
    <Editor
      key={current.id}
      initial={current}
      options={options.data}
      onDeleted={() => {
        setDeletedId(current.id);
        setCreated(null);
        list.reload();
        loaded.reload();
      }}
    />
  );
}
