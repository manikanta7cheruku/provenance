import { useCallback, useState } from "react";
import { ApiError } from "../../lib/api";
import { createResume, deleteResume, fetchOptions, fetchResume, fetchResumes, saveResume } from "../../lib/studio-api";
import type { ResumeContent, ResumeDocument, StudioContent, StudioOptions } from "../../lib/studio-api";
import { useAsync } from "../../lib/useAsync";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { ActionButton, ConfirmDialog, Notice, PageHeader, Section, SegmentedControl, Skeleton, Status } from "../../ui";
import { browserMeasure, CanvasEditor, structuredToCanvas } from "./canvas";
import type { CanvasDoc } from "./canvas";
import { fontFaceCss, FONT_FILES } from "./canvas/css";
import { allElements, isCanvas } from "./canvas/types";
import { richText } from "./canvas/rich";
import { ContentEditor } from "./ContentEditor";
import { ExportPanel } from "./ExportPanel";
import { saveText } from "./labels";
import { Preview } from "./Preview";
import { StylePanel, TemplateChoice } from "./StylePanel";
import { useStudioDocument, usePreview } from "./useStudioDocument";
import { VersionsDialog } from "./VersionsDialog";
import "./studio.css";
import "./canvas/canvas.css";

type StartKind = "profile" | "blank";
type Layout = "canvas" | "guided";

const isGuided = (content: StudioContent): content is ResumeContent => !isCanvas(content);

/** Wait until the shipped fonts are ready, so text is measured with the fonts that will print. */
async function loadFonts(): Promise<void> {
  if (typeof document === "undefined" || !document.fonts) return;
  try {
    await Promise.all(FONT_FILES.map(([family, weight, style]) => document.fonts.load(`${style} ${weight} 12px "${family}"`)));
    await document.fonts.ready;
  } catch {
    // A font that cannot load falls back to a system font. The resume is still laid out.
  }
}

/** Lay a guided resume out on canvas pages, measured in the browser, and keep the old version as a restore point. */
async function convertToCanvas(doc: ResumeDocument): Promise<ResumeDocument> {
  await loadFonts();
  const { measure, dispose } = browserMeasure();
  try {
    const canvas: CanvasDoc = structuredToCanvas(doc.content as ResumeContent, measure);
    const saved = await saveResume(doc.id, { content: canvas, revision: doc.revision, checkpoint: true });
    return { ...doc, revision: saved.revision, template: saved.template, content: canvas as unknown as StudioContent };
  } finally {
    dispose();
  }
}

function resumeName(content: StudioContent): string {
  if (isGuided(content)) return content.header.name;
  const first = allElements(content as unknown as CanvasDoc).find((e) => e.kind === "text" && e.body);
  return first && first.kind === "text" ? richText(first.body).split("\n")[0]!.slice(0, 80) : "";
}

function StudioFonts() {
  return <style>{fontFaceCss()}</style>;
}

function StartScreen({ options, onCreated }: { options: StudioOptions; onCreated: (doc: ResumeDocument) => void }) {
  const [template, setTemplate] = useState("classic");
  const [start, setStart] = useState<StartKind>("profile");
  const [layout, setLayout] = useState<Layout>("canvas");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function create() {
    setBusy(true);
    setProblem(null);
    try {
      let doc = await createResume({ start, template });
      if (layout === "canvas") doc = await convertToCanvas(doc);
      onCreated(doc);
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "The resume could not be started. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <StudioFonts />
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
          <SegmentedControl<Layout>
            legend="Way of working"
            showLegend
            value={layout}
            onChange={setLayout}
            options={[
              { value: "canvas", label: "Free canvas" },
              { value: "guided", label: "Guided and ATS-safe" },
            ]}
          />
          <p className="field__hint">
            {layout === "canvas"
              ? "Place anything anywhere: drag, resize and edit text right on the page. A layout check tells you if a tracking system may misread it."
              : "A single column that flows by itself, easiest for applicant tracking systems. You choose the content and the design."}
          </p>
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

function GuidedEditor({
  id,
  content,
  options,
  problems,
  setContent,
  epoch,
  announce,
}: {
  id: string;
  content: ResumeContent;
  options: StudioOptions;
  problems: Record<string, string>;
  setContent: (next: ResumeContent) => void;
  epoch: number;
  announce: (text: string) => void;
}) {
  const preview = usePreview(id, content);
  const [tab, setTab] = useState<Tab>("content");
  const [pane, setPane] = useState<Pane>("edit");
  return (
    <>
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
            <ContentEditor doc={content} onChange={setContent} problems={problems} epoch={epoch} announce={announce} />
          ) : (
            <StylePanel doc={content} options={options} onChange={setContent} problems={problems} />
          )}
        </section>
        <section className="studio__view" aria-label="Preview">
          <Preview html={preview.html} paper={content.style.paper} failed={preview.failed} />
        </section>
      </div>
    </>
  );
}

function Editor({
  initial,
  options,
  onDeleted,
}: {
  initial: ResumeDocument;
  options: StudioOptions;
  onDeleted: () => void;
}) {
  const doc = useStudioDocument<StudioContent>(initial);
  const [epoch, setEpoch] = useState(0);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [converting, setConverting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  useDocumentTitle("Resume studio");

  const announce = useCallback((text: string) => setMessage(text), []);
  const content = doc.content;

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

  async function toCanvas() {
    setBusy(true);
    setProblem(null);
    try {
      await doc.flush();
      const converted = await convertToCanvas({ ...initial, revision: doc.getRevision(), content });
      doc.replace(converted);
      setEpoch((n) => n + 1);
      setConverting(false);
      announce("Your resume is now on the free canvas. You can go back from Earlier versions.");
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "The resume could not be moved to the canvas. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  const problems = Object.entries(doc.problems);
  return (
    <>
      <StudioFonts />
      <PageHeader
        title="Resume studio"
        description={
          isGuided(content)
            ? "Edit on the left. The page on the right is what the PDF will look like."
            : "Drag, resize and edit anything on the page. What you see is what the PDF will print."
        }
      />

      <div className="studio__bar">
        <p role="status" className="studio__save">
          <Status
            tone={doc.state === "saved" ? "ok" : doc.state === "error" || doc.state === "conflict" ? "danger" : "neutral"}
            label={saveText(doc.state, doc.savedAt)}
          />
        </p>
        <div className="studio__actions">
          {isGuided(content) ? <ActionButton onClick={() => setConverting(true)}>Move to the free canvas</ActionButton> : null}
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

      {isGuided(content) ? (
        <GuidedEditor
          id={initial.id}
          content={content}
          options={options}
          problems={doc.problems}
          setContent={doc.setContent}
          epoch={epoch}
          announce={announce}
        />
      ) : (
        <CanvasEditor
          doc={content as unknown as CanvasDoc}
          onChange={(next) => doc.setContent(next as unknown as StudioContent)}
          options={options}
          epoch={epoch}
          announce={announce}
        />
      )}

      <Section title="PDF">
        <ExportPanel resumeId={initial.id} beforeExport={doc.flush} fileName={resumeName(content)} />
      </Section>

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
        open={converting}
        title="Move to the free canvas?"
        confirmLabel="Move to the canvas"
        busy={busy}
        onCancel={() => setConverting(false)}
        onConfirm={() => void toCanvas()}
      >
        <p>
          Every section becomes boxes you can move anywhere. The guided version is kept as an earlier version, so you can go back from Earlier versions.
        </p>
      </ConfirmDialog>
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
  const loaded = useAsync(async (signal) => (first ? fetchResume(first, signal) : null), [first]);
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
