# ADR-0034: Free canvas editor

Status: Accepted (checkpoint 2.2). The spike passed and WeasyPrint stays. Builds on [ADR-0024](0024-resume-studio-editor-approach.md), [ADR-0025](0025-resume-pdf-rendering.md) and [ADR-0033](0033-resume-studio-document-and-saving.md).

## Context
After the structured editor of 2.1 was built, the owner compared it with Canva-style tools and judged the missing freedom to be the main gap against other resume builders: a person must be able to write their name, move it to the right, nudge it with the arrow keys, and place and resize anything on the page, editing the text right there, with changes from the side panel appearing on the page without delay.

ADR-0024 had deferred a free canvas because free positioning weakens the structure that tailoring, ATS checks and page breaks rely on. The decision is now to build it anyway, and to keep as much of that structure as the canvas allows.

## Problem
How can a resume be freely positioned without becoming a design tool that produces unreadable files, and how is the page drawn instantly in the browser while the PDF still matches?

## Options considered
| Question | Options | Direction |
|---|---|---|
| Model | free-form drawing, a structured document with a position per element | Elements with a kind (text, line, shape), a box in millimetres on a page, a z-order, and content. Content stays structured text, so tailoring and checks still work. The 2.1 structured document converts to canvas elements |
| Drawing | server HTML for each change, a browser renderer from local state | A browser renderer from local state. Typing, dragging and resizing must be instant. The server only validates and saves |
| PDF | the same Python renderer, the browser's own print, a headless browser | Decided by a spike. The canvas HTML and CSS are also given to the PDF engine. If WeasyPrint matches on positioned layouts it stays, otherwise headless Chromium replaces it |
| Text editing | a separate side form only, in place on the page | In place on the page with the 2.1 rich text editor, plus the side panel, both editing one state |
| Undo | per field, global command history | One command history that covers every edit, including moves and style changes |
| ATS | ignore, warn | Warn, with the reason, when elements form columns, overlap or sit over shapes. Reading order for the PDF is top to bottom then left to right. The structured mode remains for ATS-safe resumes |
| Images | include, defer | Defer. Uploaded images need their own safety work (type checks, re-encoding, size limits, privacy of metadata) |
| Accessibility | pointer only, full keyboard | Full keyboard and screen reader support is a requirement, not a polish step. Selection, moves, resize, layers, grouping and deleting all work without a pointer, with announcements |

## Spike result (checkpoint 2.2)
Five positioned layouts were drawn three ways: by the canvas in the browser (the real editor), by WeasyPrint, and by Edge's own print engine. The layouts were a header with a name and a date row, two columns, a right-aligned name and contacts, justified text with three type sizes and capitals, and a serif-only page. Every word was matched between the canvas and each PDF, and positions were compared after removing the constant offset between a line box and a glyph box.

| Layout | Words matched | Largest horizontal difference | Largest vertical difference (after the offset) |
|---|---|---|---|
| header, role, dates, bullets | 28 of 29 | 0.03 mm | 0.07 mm (WeasyPrint), 0.21 mm (Edge) |
| two columns | 110 of 110 | 0.05 mm | 0.07 mm, 0.19 mm |
| right-aligned name and dates | 54 of 54 | 0.03 mm | 0.01 mm, 0.19 mm |
| justified, sizes, capitals | 125 of 128 | 0.03 mm | 0.20 mm, 0.10 mm |
| serif body | 46 of 46 | 0.01 mm | 0.00 mm, 0.05 mm |

The unmatched words are the ones set in capitals by CSS: the PDF text says EXPERIENCE where the screen says Experience. Both engines agree with the canvas to a few hundredths of a millimetre across and a fifth of a millimetre down, which is below what a person can see. **Decision: WeasyPrint stays. Chromium is not needed.** Not measured: a full page of dense text, other fonts, and many concurrent renders.

The spike also found a real problem that the layouts alone did not show: a PDF keeps text in the order it was drawn, and the PDF engine draws by stacking order, so the box added last was read last wherever it sat. See "Drawing order" below.

## As built
- **Model.** Version 2 of the resume content: `pages` of `elements`. An element is a text box (rich text, font role, size, color, alignment, line height, capitals) or a shape, in millimetres. A rule is a thin shape. Up to 3 pages and 150 elements. Validated on the server by `pv_domain.resume_canvas.validate_canvas` against a whitelist: positions must stay on the page, colors are a name or a hex code, rich text follows the same rules as version 1.
- **One CSS, two drawers.** The server writes each box's CSS (`element_css`) and the browser writes the same (`css.ts`). A golden file, `tests/fixtures/canvas_css_golden.json`, is checked by a Python test and a TypeScript test, so a change on one side fails the other.
- **Text boxes are as tall as their text.** The browser measures the content and stores the height, so nothing is cut off. The stored height is a minimum, and the server trims a height that would pass the page bottom instead of refusing it.
- **Drawing order.** `paint_order` draws in reading order (top to bottom, then left to right) except where two boxes overlap, where the one added later stays on top. The picture is identical and the PDF text is in the order a person reads. Tested on the real PDF.
- **Editing.** Pointer: select, shift-select, marquee, drag with snapping to the page edges, margins, page centre and other elements, resize by handles (a text box changes only its width), double press to edit in place. Keyboard: Tab through elements in reading order, arrows nudge by 0.5 mm (Shift 5 mm, Ctrl 0.1 mm), Alt with arrows resizes, Enter edits, Delete removes, Ctrl+D duplicates, Ctrl+G groups, Ctrl+Z and Ctrl+Shift+Z undo and redo, Ctrl+[ and ] reorder. Side panel: exact numbers for position and width, text style, the same rich text field (kept in step with the page), layers with forward, backward and lock, page and style.
- **Undo.** One history for every edit. Quick changes of the same kind (a drag, a held arrow key, typing) are one step.
- **Moving from guided.** The guided document is laid out on the canvas by measuring it in the browser, and the guided version is kept as an earlier version.
- **Layout check.** In plain words, with the reason: overlapping text, text boxes side by side as columns, text on a filled shape (these can make a tracking system misread), and small text, text near the page edge, pale text (notes). It is advice and never blocks anything.
- **Small screens.** Below about 980 pixels the page is shown and the PDF can be made, but editing is switched off with a sentence saying why. The guided editor is the way to edit on a phone.

## Decision (as planned)
1. Add checkpoint 2.2, before templates, because templates become canvas layouts.
2. Start with a spike: draw the five sample resumes plus positioned layouts (columns, a right-aligned name, overlapping text and a line) with the browser and with WeasyPrint and Chromium, and compare text positions, wrapping, page breaks and reading order. Record the result here and in ADR-0025.
3. Build the model, the browser renderer, selection and handles, snapping guides, keyboard moves and resize, in-place text editing, alignment and distribution, layers, lock and group, undo and redo, zoom, rulers and a margin grid, then the ATS warning.
4. Keep the server validating every save against a whitelist: element kinds, bounds inside the page, size limits, text through the same rich text rules as 2.1.
5. Keep revisions, autosave, restore points and PDF export from ADR-0033 unchanged.

## Why
The aim is a tool that is as free as Canva and understands what a resume is. Keeping the content structured and checking the layout gives suggestions, tailoring and an ATS warning that a pure drawing tool cannot offer.

## Consequences
- This is the largest feature so far. The spike may take a day or more and may change the PDF engine.
- Drawing in the browser and in the PDF engine means two renderers of positioned layout. The fidelity test becomes a permanent part of the test suite.
- The preview route of 2.1 (a server request per pause) is replaced for canvas resumes by local drawing. Structured resumes can keep it until they are converted.
- Free positioning makes bad documents possible. The ATS warning, bounds checks and a "reset to template layout" action are the guardrails.
- Touch and small screens need their own design. A phone cannot drag precisely, so the first release treats the canvas as a larger-screen feature and keeps the structured editor for phones.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Everything runs in the browser except saving and the PDF |
| 100 | Same. Documents stay small JSON |
| 10,000 | PDF rendering load is unchanged from 2.1. Saves are small |

## Revisit when
The spike shows neither engine matches the canvas, positioned layouts cause too many bad documents in practice, or images become necessary.
