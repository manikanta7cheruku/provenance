# ADR-0033: Resume studio document, saving, versions and exports

Status: Accepted (checkpoint 2.1). Builds on [ADR-0024](0024-resume-studio-editor-approach.md), [ADR-0025](0025-resume-pdf-rendering.md), [ADR-0015](0015-postgres-rls-as-defense-in-depth.md) and [ADR-0022](0022-queue-semantics-and-system-tables.md).

## Context
The studio lets a person build a resume with real formatting control and download a PDF that looks like the preview. Later checkpoints add more templates (2.2) and tailoring that changes sentences (2.3), so the resume must stay structured, must be safe to render from anything a browser sends, and must never be silently overwritten.

## Problem
What is stored, who renders it, how are two tabs kept from overwriting each other, how is an earlier version recovered, and how is a PDF made and handed back?

## Options considered
| Question | Options | Result |
|---|---|---|
| What is stored | HTML from the editor, structured JSON | Structured JSON: sections, blocks, rich text as a small node tree, style as named tokens. No markup is ever stored |
| Who validates | the editor, the browser, the server | The server, on every save and every preview, against a whitelist. The result is a clean copy; unknown keys, nodes and marks are refused or dropped |
| Who draws it | the browser for the preview and a library for the PDF, one renderer | One renderer in pure Python (`pv_domain.resume_render`) used for both. The preview is that HTML in an iframe with no scripts |
| Preview freshness | draw in the browser, ask the server | Ask the server after a short pause. Costs a request per pause, keeps one layout in the product |
| Concurrent edits | last write wins, a revision number as a lock | A revision number. A save says which revision it started from. A stale save is refused with a plain message and nothing is overwritten |
| Autosave | on every key, after a pause | After a 1.5 second pause, one save at a time, another follows if typing continued. A save is skipped when nothing changed |
| Undo across sessions | none, versions | Restore points: the content being replaced is kept at most every two minutes, or on request, up to 20. Restoring keeps the present content as a version first |
| How many resumes | a table constraint, a setting | A setting (`STUDIO_MAX_RESUMES`, default 1), so plans can change it without a migration. Entitlements replace it at 3.3 |
| Where PDFs are made | in the request, in the worker | In the worker as a queue task, so a slow render cannot hold an API worker and retries follow ADR-0022 |
| Where PDFs live | public URL, private storage | Private storage under a server-made key. Downloaded only by the owner through the API |
| PDF count | unlimited, capped | The newest `STUDIO_MAX_EXPORTS` (default 5) per resume. Older files are deleted |
| Fonts | web fonts from a CDN, self-hosted | Self-hosted files (IBM Plex Sans and Newsreader, SIL Open Font License) shipped in `pv_files`, with their licences. The preview loads them through a public cacheable route, the PDF engine reads them from disk |

## Decision
1. **Tables (migration 0008).** `resume_documents` (content jsonb, revision), `resume_document_versions`, `resume_exports`. Row Level Security enabled and forced on all three. A size check on content.
2. **Document.** Version 1: header (name, headline, contacts), sections (kind, title, blocks), blocks (heading, subheading, dates, location, rich body), style (template, font pair, size, spacing, margins, accent, divider, paper). Limits on sections, blocks, depth and total text. The accent color must reach 4.5:1 on white or it is refused with a sentence.
3. **First draft.** Built from profile entries by code. Every word comes from an entry, nothing is generated. Empty sections are left out.
4. **API.** `/api/v1/studio/...`: options, resumes (list, create, get, save, preview, versions, restore, delete), exports (start, list, download), fonts. Saves and previews are rate limited generously, exports 10 per hour. Another person's resume is 404. Audit events carry ids and counts, never text.
5. **Worker.** `render_resume_pdf` re-reads the current content, renders, stores, then marks ready. A render that fails is a visible failed export with a plain message. A storage hiccup is retried and becomes visible on the last attempt. A task for a deleted resume does nothing.
6. **Engine.** WeasyPrint (ADR-0025), allowed to read only the shipped fonts. Anything else it is asked to load makes the render fail closed.
7. **Cache header.** The security middleware sets `no-store` on API responses only when the route has not chosen its own header, so the fonts can be cached for a year.

## Why
Structured content is what lets tailoring and suggestions change text without touching layout. A server renderer makes the output the same everywhere and removes a whole class of stored-markup problems. Revisions and restore points make an editor that saves by itself safe to leave open.

## Consequences
- Every preview is a request. Rate limits and the short pause bound the load. A person on a slow connection sees the preview a moment after typing.
- Page breaks in the preview come from a browser and in the PDF from WeasyPrint. They agreed on all five sample resumes, and the PDF is the exact version. The screen says so.
- Fonts cover the Latin alphabet only. A name in Devanagari or another script falls back to a system font in the PDF. Adding subsets is a later change and a licence check.
- A person who edits in two tabs gets a conflict message and must load the newer version, so edits in the stale tab are lost. The unsaved text stays on screen until they choose.
- The one-resume limit is by setting, so a database-level guarantee does not exist. The service checks it inside the transaction, and two simultaneous creates could in theory produce two. Entitlements at 3.3 should add a lock.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | One worker renders on demand in under a second |
| 100 | Same. Saves and previews are small JSON requests |
| 10,000 | Preview requests dominate. Cache by content hash or render in the browser. PDF rendering gets a concurrency limit and its own workers |

## Revisit when
Preview latency or cost becomes a problem, a template needs layout WeasyPrint cannot do, scripts beyond Latin are needed, or two-person editing is wanted.
