# ADR-0034: Free canvas editor

Status: Proposed (planned for checkpoint 2.2, to be accepted after its spike). Builds on [ADR-0024](0024-resume-studio-editor-approach.md), [ADR-0025](0025-resume-pdf-rendering.md) and [ADR-0033](0033-resume-studio-document-and-saving.md).

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

## Decision (provisional)
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
