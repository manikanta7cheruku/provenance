# Resume Studio Requirements

Status: Draft (revision 2 roadmap, 2026-10-30). Delivered in checkpoints 2.1 to 2.4 (2.2 is the free canvas editor, see section 7). Decisions pending spikes are in [ADR-0024](../adr/0024-resume-studio-editor-approach.md) and [ADR-0025](../adr/0025-resume-pdf-rendering.md).

## 1. Purpose

Let a student create, customize and tailor a professional resume with much more freedom than typical builders, and with suggestions that Canva-style tools do not offer. The studio is also the free entry point of the product.

## 2. User stories

1. Create a resume from my profile entries, or start from scratch.
2. Choose among 20 or more professional templates and see my content in each one.
3. Format anything: bold, italic, underline, highlight, lists, divider lines, spacing, fonts, colors, section order, margins.
4. See suggestions while I edit: weak wording, missing numbers, vague claims, length, gaps against a chosen job.
5. Download a professional PDF that looks exactly like the preview.
6. Tailor the resume to a specific job, review every change, accept, reject or edit.

## 3. Requirements

| ID | Requirement | Checkpoint |
|---|---|---|
| FR-RES-1 | Structured editor with live preview. Content is sections, blocks and rich text. Style is separate from content | 2.1, built |
| FR-RES-2 | Formatting: bold, italic, underline, highlight, bullet and numbered lists, divider lines, spacing scale, margins, section reorder | 2.1, built |
| FR-RES-3 | Professional fonts, self-hosted, with font pairs. Font licences checked before shipping | 2.1, built with three pairs from two open licence families |
| FR-RES-4 | PDF export matching the preview, text selectable, reading order verified by test | 2.1, built. Page counts agreed on the five sample resumes |
| FR-RES-5 | At least 20 templates. Each declares an ATS-safe flag. The editor warns when edits reduce ATS safety | 2.3, built |
| FR-RES-6 | Suggestions in the editor that never add facts the profile does not support. Each suggestion shows why and is accepted, rejected or edited by the user | 2.4, built |
| FR-RES-7 | Tailoring to a job with a grounding verifier (FR-TAI-1, FR-TAI-2) | 2.4, built |
| FR-RES-8 | Free plan: one resume and rate-limited exports. Enforced by entitlements at 3.3. Until then a single configurable limit exists | 2.1 built as `STUDIO_MAX_RESUMES`, 3.3 |
| FR-RES-9 | Autosave, version history of the last N saves per resume, restore | 2.1, built (N is 20, a restore point at most every two minutes) |
| FR-RES-10 | Delete a resume removes the stored files and rows. Profile entries remain | 2.1, built |

## 4. Rules

- The studio never invents experience, skills, dates or numbers. A suggestion that needs a fact asks the user for it.
- Every generated or tailored sentence is labelled as a suggestion until the user accepts it.
- Templates are original designs or licensed assets. No copying of other products' designs.
- ATS safety is shown, not hidden. A heavily designed template is allowed and flagged.

## 5. Acceptance criteria (outline, finalized per checkpoint)

Technical: PDF text extraction returns the content in order for every template. Preview and PDF agree on page breaks in the sample set. Autosave survives a browser refresh. Rate limit returns the structured 429.

UX: a new user can produce and download a resume in under ten minutes from a parsed profile. Every control has a keyboard path. Suggestions never block typing.

Accessibility: the editor toolbar is a labelled toolbar with arrow-key navigation. Color choices show contrast results. The template gallery is navigable by keyboard. The PDF has a document title and language.

## 6A. Free canvas mode (checkpoint 2.2, added in roadmap revision 3)

Other resume builders either give templates with little freedom or give Canva-style freedom with no sense of what a resume is. The studio offers both ways of working on the same resume: the structured editor of 2.1, and a free canvas.

| ID | Requirement | Checkpoint |
|---|---|---|
| FR-RES-11 | Every element on the page is a box that can be selected, dragged, resized and moved with the arrow keys (with larger steps while a modifier key is held), with snapping guides to the margins, the page centre and other elements | 2.2, built |
| FR-RES-12 | Text is edited in place on the page. The side panel edits the same content. A change in either shows in the other at once, with no network wait | 2.2, built |
| FR-RES-13 | Multi-select, align, distribute, layers (bring forward, send back), lock, group, duplicate, delete, undo and redo that cover every edit, zoom, a margin grid and rulers | 2.2, built |
| FR-RES-14 | Lines and simple shapes as elements. Images are not in the first release | 2.2, built |
| FR-RES-15 | PDF output matches the canvas, with selectable text in reading order (top to bottom, then left to right) | 2.2, built |
| FR-RES-16 | A visible ATS-safety indicator that says when the layout uses columns, overlaps or text over shapes, with the reason | 2.2, built |
| FR-RES-17 | Every canvas action works from the keyboard, with announcements for screen readers. A person who cannot use a pointer can do everything | 2.2, built |
| FR-RES-18 | Templates (2.3) are canvas layouts. Switching a template re-flows content and keeps the person's edits where possible | 2.3, built |
| FR-RES-19 | A person can add a link (web, mail or phone) to any text, and contacts are linked automatically. Only https, http, mailto and tel are accepted, on the server and in the browser. In the PDF a link is a real link | 2.3, built |
| FR-RES-20 | At least 9 font families and 12 font pairs, all shipped with the product so a PDF never depends on the network | 2.3, built |
| FR-RES-21 | Color themes: ready-made sets of accent, text, grey and tint, each checked for readability, with custom colors that are refused when unreadable | 2.3, built |
| FR-RES-22 | Images, photos and icons on the canvas | 2.11 |
| FR-RES-23 | Editing on touch screens and phones | 2.12 |
| FR-RES-24 | Saved themes and a brand kit reused across resumes | 2.13 |

Rules: the canvas never invents content. Suggestions and tailoring (2.4) change text and never layout. The structured mode stays for people who want an ATS-safe resume with no layout work.

## 6. Open decisions

- Editor library: decided at 2.1 (TipTap), with a comparison that was not run. See ADR-0024.
- PDF engine: decided at 2.1 (WeasyPrint) after a measured spike. See ADR-0025.
- Number and style of the first three templates versus the full 20 or more: three built, the rest in 2.3 on top of the canvas.
- Canvas fidelity and the PDF engine: decided by a spike at the start of 2.2 (ADR-0034).
- Whether to add a free-form block later. Decided: yes, as the free canvas mode of checkpoint 2.2 (ADR-0034).
