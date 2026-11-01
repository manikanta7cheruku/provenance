# Checkpoint 2.2: Free canvas editor

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.2-free-canvas-editor`. Decisions: [ADR-0034](../adr/0034-free-canvas-editor.md), with the PDF engine choice of [ADR-0025](../adr/0025-resume-pdf-rendering.md) confirmed by a measurement. Runbook: [a resume PDF cannot be made](../operations/runbooks/resume-pdf-failed.md).

The owner's test of 2.1 against Canva-style tools named the main gap against other resume builders: a person must be able to place, move, resize and edit anything on the page. This checkpoint adds that, kept professional: every element is a box on the page, text is edited right where it sits, the side panel edits the same data and the two stay in step with no wait, and the PDF is the page that was drawn.

## 1. Build

**Document (version 2, no migration).** `pv_domain.resume_canvas`: pages of elements in millimetres. A text box (rich text, font role, size, color, alignment, line height, capitals) or a shape (fill, outline, corner radius). A rule is a thin shape. Up to 3 pages and 150 elements. `validate_canvas` returns a clean copy or says what is wrong at which path: positions stay on the page, colors are a name or a hex code, rich text follows the rules of version 1, unknown kinds and keys are refused or dropped. A text box taller than the page bottom is trimmed, because its height is only a minimum.

**One CSS, two drawers.** `element_css` on the server and `css.ts` in the browser write the same declarations for an element. A golden file checked by both languages keeps them equal.

**Drawing order.** `paint_order` draws in reading order, except where two boxes overlap, where the later one stays on top. A PDF keeps text in drawing order, so this is what makes the file read top to bottom and left to right.

**Canvas editor (browser).** `features/studio/canvas/`:
- Stage: pages drawn from local state, so typing and dragging are instant. Selection, shift-select, marquee, drag with snapping to page edges, margins, the page centre and other elements, eight resize handles (text boxes change width only), double press to edit text in place with the rich text editor and a format bar, guides, margin guide, zoom and fit.
- Toolbar: add text, box and rule; undo and redo; duplicate, delete, group, ungroup, lock; forward, backward, to front, to back; align (six ways) and distribute; zoom; margins; layout check.
- Side panel: element (name, rich text kept in step with the page, font, size, alignment, line spacing, color, capitals, exact position and width, shape fill, outline and radius), layers (select, forward, backward, lock), page and style (paper, margin guide, fonts, accent color, pages, move the selection to a page).
- Keyboard: Tab through elements in reading order, Space selects and Shift+Space adds, arrows nudge, Shift and Ctrl change the step, Alt with arrows resizes, Enter edits, Delete, Ctrl+D, Ctrl+G, Ctrl+A, Ctrl+Z and Ctrl+Shift+Z, Ctrl+[ and ], Ctrl+plus and minus. Every move, resize, reorder or delete is announced for screen readers.
- Undo: one history for all edits. Quick changes of the same kind are one step.
- Layout check: overlapping text, columns, text on a filled shape (can mislead a system), small text, text near the edge, pale text (notes). Advice, never blocking.
- Moving a guided resume to the canvas lays it out top to bottom by measuring each box in the browser. The guided version stays as an earlier version.

**Studio.** The start screen offers Free canvas or Guided and ATS-safe. The studio page uses the full width. Saving, versions, conflict handling and PDF export are unchanged and work for both kinds. On a narrow screen the page is shown and the PDF can be made, and editing says why it is off.

## 2. UX

- Click to select, drag to move, double press to type. Handles appear only where they work.
- What is on the page is what prints: the same fonts, the same CSS, a measured spike behind it.
- Nothing is lost: undo, earlier versions, locked elements and a delete that says it can be undone.
- The layout check says why, in words, and shows the elements it means.

## 3. Technical acceptance criteria

1. A canvas document is saved, read back and exported like a guided one. No migration was needed.
2. The server refuses elements off the page, unknown kinds, images, markup, bad colors, bad numbers and too many pages or elements, next to the field, and stores nothing.
3. The CSS of every element kind is identical on the server and in the browser (golden file, both languages).
4. The PDF has each text box where the document says, within 0.8 mm across, reads top to bottom then left to right, keeps stacking where boxes overlap, embeds the shipped fonts, has the right paper, one PDF page per canvas page, a title and a language.
5. A measured spike on five layouts: the browser canvas, WeasyPrint and Edge's print engine agree within 0.05 mm across and 0.2 mm down.
6. Moving, resizing, nudging, snapping, aligning, distributing, grouping, ordering, locking, duplicating, deleting, paging and paper changes behave as specified and never change the document they were given (unit tests).
7. A held arrow key, a drag and typing are each one undo step.
8. A locked element cannot be moved by drag, keys or the numbers.
9. The side panel and the page show the same text at once, whichever is edited.
10. A guided resume moves to the canvas with no overlapping boxes, inside the margins, with the guided version restorable.
11. Ruff, mypy, import-linter, unit, integration, PDF and web tests, and the web checks pass.

## 4. UX acceptance criteria

1. A new person can start a canvas resume from their profile and see a clean page without placing anything.
2. Every action a pointer can do has a keyboard way, and the result is announced.
3. Editing is clearly off, with a reason, on a screen too narrow for it.

## 5. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation with an element selected, with the layout check open, in the layers and page tabs, and while editing text, in light and dark. Elements are focusable groups with a name that says what they are, where they are and whether they are locked or selected. Toolbars are ARIA toolbars with arrow keys. Buttons that show text have names that contain it. Colors in the interface meet contrast, and the paper inks have their own checked tokens.

## 6. Test

| Where | What |
|---|---|
| `tests/unit/test_resume_canvas.py` | validation, reading and paint order, the HTML, the shared CSS golden file |
| `tests/pdf/test_canvas_pdf.py` | the real engine: positions, order, fonts, paper, pages, bullets, title |
| `tests/integration/test_studio_canvas.py` | saving, refusals, trimming, preview, moving from guided and restoring, the export task, isolation |
| `src/features/studio/canvas/engine.test.ts` | the golden CSS, geometry, every document edit, history, the layout check |
| `src/features/studio/canvas/convert.test.ts` | laying a guided resume out |
| `e2e/canvas.spec.ts` | drag, snap, resize, nudge, undo, edit in place, side panel, align, group, layers, lock, pages, paper, zoom, marquee, keyboard selection, layout check, narrow screen, axe in both themes |

## 7. Document

[ADR-0034](../adr/0034-free-canvas-editor.md) (accepted, with the spike result and what was built), [ADR-0025](../adr/0025-resume-pdf-rendering.md), [resume-studio-requirements.md](../product/resume-studio-requirements.md) (FR-RES-11 to FR-RES-17 built), [data-model.md](../architecture/data-model.md), [threat-model.md](../security/threat-model.md), the [runbook](../operations/runbooks/resume-pdf-failed.md), [ux-specification.md](../product/ux-specification.md), the roadmap status.

## 8. Commit

```
feat(studio): add the free canvas editor with drag, resize, in-place editing and a layout check
```

## 9. Interview defense

You should be able to explain:
- Why the canvas keeps structured content and positions, and not pixels.
- How the page can update with no lag while the PDF still matches: local state, one CSS in two languages, a golden file, a measured spike.
- What the spike measured, how (word positions matched across three renderers), and the one thing it did not show that a test then found: PDF text is kept in drawing order.
- Why text boxes are as tall as their text and what the server does with a height.
- How snapping, undo coalescing and the double-press detection work, and why the browser's own double-click could not be used.
- What the layout check is for and why it never blocks.
- What a keyboard-only person can do and how they know it happened.

## 10. What was verified and what was not

Verified: all tests above. A live run on the Docker stack through the real API, queue, worker and engine with a canvas document. The word-position spike on five layouts. Screenshots of the editor.

Not verified: a real person using the editor (your test is next), dense full-page text and other fonts in the spike, many concurrent renders, touch devices (the canvas is a larger-screen feature in this release), images (not included), and a screen reader session by a person (axe and labels were checked, not a spoken run).

## 11. Run it yourself

```
.\scripts\pv.ps1 up
```
Open Resume studio. If you have a resume already, press Move to the free canvas. Drag things, use the arrow keys, double-click text, undo, check the Layout check, and make a PDF.
