# ADR-0025: Resume PDF rendering

Status: Accepted (checkpoint 2.1). **WeasyPrint**, chosen after a measured comparison with headless Chromium. Related to [ADR-0024](0024-resume-studio-editor-approach.md) and [ADR-0033](0033-resume-studio-document-and-saving.md).

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

## Spike result (checkpoint 2.1)
Five sample resumes (a fresher with one page, a six-job experienced resume, a compact dense one, a Letter-size large-type relaxed one, and one with highlights and dotted rules) were rendered from the same HTML and CSS by both engines in clean `python:3.12-slim-bookworm` containers on 2026-10-31. Fonts were the shipped IBM Plex Sans and Newsreader.

| Measure | WeasyPrint 70 | Chromium (Playwright, headless) |
|---|---|---|
| Time per resume (warm) | 0.24 to 0.42 s | 0.07 to 0.13 s |
| PDF size | 16 to 60 KB | 18 to 25 KB |
| Pages (five samples) | 2, 2, 1, 1, 2 | 2, 2, 1, 1, 2 (identical) |
| Text in reading order | yes, all five | yes, all five |
| Title in the file | yes | yes |
| Install time and size | 33 s, 86 MB of Python packages plus two small system libraries | 305 s, 681 MB browser plus system dependencies |
| Python process memory | 73 MB peak | 42 MB, but the browser process was not measured |

Both engines produced selectable, ordered text and the same page counts on all five samples. Chromium is about three times faster per document and matches a browser preview most closely. WeasyPrint needs a fraction of the install and fits a Python worker without a second runtime. Both are well under a second.

**Decision: WeasyPrint.** The operational cost of shipping and running a browser in the worker is not justified when the measured output is equivalent for these resumes. Chromium stays the fallback if a template needs CSS that WeasyPrint cannot draw.

**What the spike did not settle.** Memory of the Chromium process, behavior with many concurrent renders, and complex templates (the two-column ones planned for 2.3). The first Chromium run silently fell back to a system font because the fonts were not reachable from the page, which shows that every engine needs a test that the shipped fonts are really embedded. `tests/pdf/test_resume_pdf.py` asserts it. The same test found, in the real worker, a fetcher that made WeasyPrint fall back to DejaVu Sans, which no unit test of the HTML could have caught.

## Reopened by the canvas editor
The measured choice above was made for flowing documents. The free canvas of checkpoint 2.2 ([ADR-0034](0034-free-canvas-editor.md)) draws absolutely positioned boxes in the browser, where a mismatch with the PDF engine is easier to see. The fidelity spike on positioned layouts was run at the start of 2.2 and WeasyPrint passed: on five layouts it matched the canvas to 0.05 mm across and 0.2 mm down, the same as Edge's print engine. The decision stands. Details are in [ADR-0034](0034-free-canvas-editor.md). The spike also showed that a PDF reads text in drawing order, which the canvas renderer now controls.

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
