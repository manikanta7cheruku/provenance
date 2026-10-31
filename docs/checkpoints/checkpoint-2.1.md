# Checkpoint 2.1: Resume studio core

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.1-resume-studio-foundation`. Decisions: [ADR-0033](../adr/0033-resume-studio-document-and-saving.md), with [ADR-0024](../adr/0024-resume-studio-editor-approach.md) and [ADR-0025](../adr/0025-resume-pdf-rendering.md) accepted. Runbook: [a resume PDF cannot be made](../operations/runbooks/resume-pdf-failed.md).

A person opens the Resume studio, starts from their profile or a blank page, edits with real formatting control, sees the page as it will print, and downloads a PDF. It is the free entry point of the product: one resume, rate-limited exports.

## 1. Build

**Database (migration 0008, literal SQL).** `resume_documents` (structured JSON content, a revision number), `resume_document_versions` (up to 20 restore points), `resume_exports` (each PDF, with its private storage key). Row Level Security enabled and forced on all three.

**Domain.** `pv_domain.resume_doc`: the document model, a whitelist validator that returns a clean copy, rich text rules (paragraphs, lists, bold, italic, underline, highlight), style tokens, an accent color that must be readable on white, three templates with an ATS-safe flag, and a first draft built only from profile entries. `pv_domain.resume_render`: one renderer, pure Python, used by the preview and the PDF.

**Files.** `pv_files.render`: WeasyPrint with a fetcher that may read only the shipped fonts. Eight font files (IBM Plex Sans and Newsreader, regular, italic, semibold, semibold italic) with their SIL Open Font License texts.

**Persistence.** `pv_persistence.studio`: revision-checked saves, restore points, exports, deletion that returns the stored file keys.

**API.** `/api/v1/studio`: options, resumes (create, read, save, preview, delete), versions and restore, exports and download, and a public cacheable route for the fonts. The security middleware no longer overrides a route that sets its own cache header.

**Worker.** `render_resume_pdf`: renders the current content, stores the PDF privately, records steps, fails visibly, retries storage trouble, ignores deleted or finished exports.

**Web.** `/studio` and a "Resume studio" navigation item: a start screen with template cards, the editor (details, sections and items with move and remove, rich text with an ARIA toolbar, design panel with template, fonts, size, spacing, margins, lines, paper and accent), a live preview scaled to fit, autosave with a clear status, earlier versions, delete, and the PDF panel.

**Tools.** `.\scripts\pv.ps1 pdftest` runs the PDF engine tests inside the image. CI installs the native libraries and runs them directly. `STUDIO_MAX_RESUMES` and `STUDIO_MAX_EXPORTS` settings.

## 2. UX

- The page on screen is the page that prints. The preview says how many pages and that the PDF is the exact version.
- Saving is automatic, one clear line says where things stand, and a second tab cannot silently overwrite the first.
- Every control has a keyboard path. Move buttons announce the new position. Removing a section asks first and says it can be recovered from earlier versions.
- A color that is too light to read is refused with a sentence, not silently changed.

## 3. Technical acceptance criteria

1. Migration 0008 applies after 0007 and reverses. Row Level Security is forced on all three tables. Other tenants see nothing and a forged insert is refused.
2. A document with an unknown node, a link, an image, a mark outside the list, too much nesting, too many sections or items, or a too light accent is refused next to the field. Unknown keys are dropped. Nothing is stored on a refusal.
3. Rendering escapes every string, emits only whitelisted tags and no attribute that carries a script or an address. The only addresses are the shipped fonts.
4. A save from an old revision is refused and changes nothing. Restore points follow the two-minute rule and a request forces one. Only the newest 20 are kept. Restoring keeps the present content.
5. The first draft contains only words from profile entries.
6. One resume per person by default, and deleting frees the slot. Deleting removes versions, exports, files and waiting tasks, and leaves profile entries.
7. An export is made by the worker, stored under a server-made key, downloaded only by its owner with attachment and no-store headers, with a safe file name. A second export while one runs is refused. Only the newest five are kept.
8. The PDF has selectable text in reading order, bullets before their text, a title and a language, the right paper size, and the shipped fonts embedded, never a system fallback. A long resume flows onto more pages without losing text.
9. The PDF engine fetches nothing but the shipped fonts, and fails closed when asked.
10. A render failure is a visible failure. A storage failure is retried, visible on the last attempt. A task for another owner, a stale or finished export does nothing.
11. Ruff, mypy, import-linter, unit, integration and PDF tests, and the web checks pass.

## 4. UX acceptance criteria

1. A new person can start from their profile and download a PDF without reading instructions.
2. Autosave status is always visible. A conflict explains what happened and offers the next step.
3. At 375 pixels wide the editor and preview are shown one at a time and nothing scrolls sideways.

## 5. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the start screen, the editor (content and design), the versions dialog, the delete dialog and the export states, in light and dark. The preview frame has a title. The formatting toolbar is a labelled toolbar with one tab stop and arrow, Home and End keys. Buttons that show text have names that contain it. Highlight colors pass contrast in both themes.

## 6. Test

| Where | What |
|---|---|
| `tests/unit/test_resume_doc.py` | validation, rich text, style, first draft |
| `tests/unit/test_resume_render.py` | escaping, tag whitelist, reading order, style tokens |
| `tests/pdf/test_resume_pdf.py` | the real engine: text order, fonts embedded, bullets, title, paper, long documents, nothing else fetched. Runs in the image and in CI |
| `tests/integration/test_studio.py` | API, saving and conflicts, versions, preview, fonts, exports and the worker task, deletion, isolation, audit |
| `src/features/studio/studio.test.tsx` | document edits, the editor, the design panel, autosave |
| `e2e/studio.spec.ts` | axe in both themes, the flows, keyboard toolbar, conflict, export, restore, delete, narrow screen |

## 7. Document

[ADR-0033](../adr/0033-resume-studio-document-and-saving.md), [ADR-0024](../adr/0024-resume-studio-editor-approach.md), [ADR-0025](../adr/0025-resume-pdf-rendering.md), [data-model.md](../architecture/data-model.md), [privacy.md](../compliance/privacy.md), [threat-model.md](../security/threat-model.md), [operator-commands.md](../operations/operator-commands.md), the [runbook](../operations/runbooks/resume-pdf-failed.md) and index, [resume-studio-requirements.md](../product/resume-studio-requirements.md), the roadmap status.

## 8. Commit

```
feat(studio): add the resume studio with a rich text editor, live preview and PDF export
```
Include the updated `uv.lock` and `apps/web/package-lock.json`. New dependencies: `weasyprint` (BSD) for the PDF, and `@tiptap/*` (MIT) for the editor.

## 9. Interview defense

You should be able to explain:
- Why the resume is structured data and not HTML, and what that protects.
- Why one server renderer feeds both the preview and the PDF, and what still differs (two engines).
- How the revision number stops two tabs overwriting each other.
- How the PDF engine was chosen: what was measured, what was not, and the bug the real test caught (fonts silently falling back).
- Why the accent color is refused instead of adjusted.
- Why bullets are real text in the flow, and what goes wrong with list markers in a PDF.
- What the ATS-safe flag means and why it is shown, not hidden.

## 10. What was verified and what was not

Verified: all tests above, including 25 PDF engine tests inside the Docker image. A live run on the Docker stack through the real API, queue, worker and engine: create from profile, save, preview, export, download, reading order, title and language, embedded fonts, delete. The three templates were drawn to images and inspected.

Not verified: how a person finds the editor to use in practice (the owner's own test is the next step), behavior with several people rendering at once, names in scripts other than Latin, and a comparison of the editor library with Lexical. Page-break agreement between preview and PDF was checked on five samples only.

## 11. Run it yourself

```
.\scripts\pv.ps1 up
```
Open Resume studio, start from your profile, edit, press Make a PDF. Try the keyboard: Tab to a formatting toolbar, arrow keys between buttons.
