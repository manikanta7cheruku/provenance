# ADR-0024: Resume studio editor approach

Status: Proposed (decided at checkpoint 2.1 after a short spike). Builds on [ADR-0019](0019-frontend-architecture-and-boundaries.md).

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

## Revisit when
The spike shows the chosen library cannot support a required control, or users request free positioning in volume.
