# ADR-0024: Resume studio editor approach

Status: Accepted (checkpoint 2.1). TipTap, with the limits described under "Decision at 2.1". Builds on [ADR-0019](0019-frontend-architecture-and-boundaries.md).

## Context
The product includes a resume studio (see [resume-studio-requirements.md](../product/resume-studio-requirements.md)). Users should have much more freedom than in typical resume builders: rich text, divider lines, spacing, fonts, colors and section order, with a live preview and suggestions. Canva-style tools offer freedom without intelligence. Typical builders offer templates without freedom.

## Problem
How is a resume represented and edited so that users have real formatting control, the content stays structured (for evidence checks, tailoring and ATS safety), and the preview and the PDF agree?

## Options considered
| Option | Result |
|---|---|
| Fully free-form canvas (drag anything anywhere) | Maximum freedom. Large engineering cost, weak structure for tailoring and ATS, easy to produce unreadable documents. Deferred, not rejected |
| Structured document model plus rich text inside blocks, with style controls per block and per template | Chosen for the first release. Content stays structured, formatting is controlled by style tokens, preview and PDF render the same HTML and CSS |
| Fixed templates with only text fields | Same as existing builders. Fails the freedom goal |

## Decision
1. A resume is a structured document: sections, blocks inside sections, and rich text inside blocks. Style is separate from content (template plus overrides).
2. Rich text uses a maintained editor library built on a document model (candidates: TipTap or ProseMirror, Lexical). The choice is made in a time-boxed spike at 2.1. Current licence terms are read from the official repository before adoption.
3. Style controls are tokens: font pair, size scale, colors, line and divider styles, spacing scale, margins. Free positioning is out of scope for the first release.
4. Every template declares an ATS-safe flag. The editor warns when customization reduces it.
5. The tailoring and suggestion features operate on the structured content, never on the rendered output.

## Why
Structure is what makes the product's differentiators possible: evidence grounding, per-job tailoring and claim verification. A free canvas would lose that structure.

## Consequences
- The editor is a large frontend feature and gets its own checkpoints (2.1, 2.2).
- A free-form mode can be added later as an additional block type if users ask for it.
- The frontend boundary rules still apply: the editor lives in one feature folder and does not import other features.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Editing is client side. Saving is a small JSON document |
| 100 | Same. Autosave with debounce |
| 10,000 | Same. Document size is small. Load comes from PDF rendering, see ADR-0025 |

## Decision at 2.1
The editor library is **TipTap** (ProseMirror underneath), using only its open source packages: `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-highlight` and `@tiptap/pm`. Their licence is MIT, read from the package metadata on 2026-10-31. The paid TipTap extensions are not used.

The schema is cut down to what the resume model allows: paragraphs, bulleted and numbered lists, hard breaks, and the marks bold, italic, underline and highlight. Headings, links, images, code, quotes and rules are switched off, so pasted content cannot bring them in. The server validates the JSON again ([ADR-0033](0033-resume-studio-document-and-saving.md)).

**What was and was not measured.** The planned side-by-side spike with Lexical was not run. TipTap was chosen because its document model is JSON that maps directly to the structured resume, its schema can be restricted, and its React binding allowed a toolbar that follows the ARIA toolbar pattern. Lexical may serve equally well. This is a judgment from reading and building, not a measured comparison, and it can be reversed because only `RichField.tsx` touches the library.

## Revisit when
The spike shows the chosen library cannot support a required control, or users request free positioning in volume.
