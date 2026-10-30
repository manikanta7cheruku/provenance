# ADR-0025: Resume PDF rendering

Status: Proposed (decided at checkpoint 2.1 after a spike with sample resumes). Related to [ADR-0024](0024-resume-studio-editor-approach.md).

## Context
PDF quality is a core promise of the resume studio. The owner wants the best and most professional output. Recruiters and applicant tracking systems read these files, so the text must stay selectable and in a sensible reading order.

## Problem
Which rendering approach gives the highest typographic fidelity, matches the live preview, and is operable by a small team?

## Options considered
No option has been measured yet. The characteristics below describe the usual trade-offs and must be confirmed by the spike.

| Option | Expected strengths | Expected concerns |
|---|---|---|
| Headless Chromium rendering the same HTML and CSS as the preview | Best match with the preview, full modern CSS, embedded fonts | Heavier runtime, needs a browser in the worker image, memory use per render |
| WeasyPrint (HTML and CSS to PDF) | Lighter, Python-native | Narrower CSS support, preview may differ from the output |
| LaTeX | Excellent typography | Hard to customize, hard to map from a live editor |
| JavaScript PDF library | Runs without a server browser | Layout code duplicated outside the preview, fidelity risk |

## Decision
Provisional: render with headless Chromium in the worker from the same HTML and CSS the preview uses. The spike at 2.1 renders at least five sample resumes with each of the two leading options and compares fidelity, text extraction, file size, render time, memory use and operational cost. The result and any change of direction are recorded here.

Independent of the engine:
- Fonts are self-hosted and embedded. Font licences are checked before a font is shipped.
- Rendering runs as a queue task so it cannot block the API and respects the retry rules of ADR-0022.
- The file is stored through the `FileStorage` interface and downloadable only by its owner.
- Text extraction from the generated PDF is tested to confirm the reading order.

## Why
A single source of layout (HTML and CSS) removes the "preview differs from PDF" class of bugs. Measuring before committing avoids choosing on reputation.

## Consequences
- The worker image grows if Chromium is chosen.
- A render concurrency limit is needed and is configured, not hard coded.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | One worker, renders on demand |
| 100 | Same, with a concurrency limit |
| 10,000 | Dedicated render workers or a smaller engine, measured at that time |

## Revisit when
The spike contradicts the expectations above, or render cost per document becomes a material share of cost.
