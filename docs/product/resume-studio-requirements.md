# Resume Studio Requirements

Status: Draft (revision 2 roadmap, 2026-10-30). Delivered in checkpoints 2.1 to 2.3. Decisions pending spikes are in [ADR-0024](../adr/0024-resume-studio-editor-approach.md) and [ADR-0025](../adr/0025-resume-pdf-rendering.md).

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
| FR-RES-1 | Structured editor with live preview. Content is sections, blocks and rich text. Style is separate from content | 2.1 |
| FR-RES-2 | Formatting: bold, italic, underline, highlight, bullet and numbered lists, divider lines, spacing scale, margins, section reorder | 2.1 |
| FR-RES-3 | Professional fonts, self-hosted, with font pairs. Font licences checked before shipping | 2.1 |
| FR-RES-4 | PDF export matching the preview, text selectable, reading order verified by test | 2.1 |
| FR-RES-5 | At least 20 templates. Each declares an ATS-safe flag. The editor warns when edits reduce ATS safety | 2.2 |
| FR-RES-6 | Suggestions in the editor that never add facts the profile does not support. Each suggestion shows why and is accepted, rejected or edited by the user | 2.3 |
| FR-RES-7 | Tailoring to a job with a grounding verifier (FR-TAI-1, FR-TAI-2) | 2.3 |
| FR-RES-8 | Free plan: one resume and rate-limited exports. Enforced by entitlements at 3.3. Until then a single configurable limit exists | 2.1, 3.3 |
| FR-RES-9 | Autosave, version history of the last N saves per resume, restore | 2.1 |
| FR-RES-10 | Delete a resume removes the stored files and rows. Profile entries remain | 2.1 |

## 4. Rules

- The studio never invents experience, skills, dates or numbers. A suggestion that needs a fact asks the user for it.
- Every generated or tailored sentence is labelled as a suggestion until the user accepts it.
- Templates are original designs or licensed assets. No copying of other products' designs.
- ATS safety is shown, not hidden. A heavily designed template is allowed and flagged.

## 5. Acceptance criteria (outline, finalized per checkpoint)

Technical: PDF text extraction returns the content in order for every template. Preview and PDF agree on page breaks in the sample set. Autosave survives a browser refresh. Rate limit returns the structured 429.

UX: a new user can produce and download a resume in under ten minutes from a parsed profile. Every control has a keyboard path. Suggestions never block typing.

Accessibility: the editor toolbar is a labelled toolbar with arrow-key navigation. Color choices show contrast results. The template gallery is navigable by keyboard. The PDF has a document title and language.

## 6. Open decisions

- Editor library (ADR-0024 spike).
- PDF engine (ADR-0025 spike).
- Number and style of the first three templates versus the full 20 or more.
- Whether to add a free-form block later.
