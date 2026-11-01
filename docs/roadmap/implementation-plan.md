# Master Implementation Plan

Status: Decided (Phase 0), revised 2026-10-30 (revision 2, see section 13). This is the single roadmap. Amendments from the review of Phase 0 are incorporated here.

## 1. Release phases

| Phase | Name | Tag |
|---|---|---|
| 0 | Design and Architecture | v0.0.1 |
| 1 | Foundation and Core Intelligence | v0.1.0 |
| 2 | Resume Studio, Discovery and User Workflow | v0.2.0 |
| 3 | Intelligence, Monetization and Production | v0.3.0 |

Each phase is cut into checkpoints. Each checkpoint is runnable, tested, documented and committed on its own.

### 1.1 Status

29 checkpoints in total. Twelve are done and merged (1.1 to 1.9 and 2.1 to 2.3). Checkpoint 2.4 is built and awaiting merge. Sixteen remain after it. Revision 3 added checkpoint 2.2, the free canvas editor. Revision 4 adds 2.11 to 2.13 for images and icons, touch editing and saved themes, which the owner asked for after testing 2.2. They sit at the end of Phase 2 so earlier numbers stay stable, and can be pulled forward on request.

| Checkpoint | State |
|---|---|
| 1.1, 1.2, 1.3, 1.4, 1.5, 1.6 | Done, merged, CI green |
| 1.7 | Done and merged |
| 1.8 | Done and merged |
| 1.9 | Done and merged |
| 2.1 | Done and merged |
| 2.2 | Done and merged |
| 2.3 | Done and merged |
| 2.4 | Built on branch phase-2/checkpoint-2.4-resume-tailoring, awaiting review and merge |
| 2.5 to 2.13 | Not started |
| 3.1 to 3.7 | Not started |

## 2. Checkpoint loop

```
Learn -> Build -> Test -> Document -> Commit -> Explain
```

At the end of every checkpoint a report states: what was built, what was tested, what was documented, the architectural decision made, why, trade-offs considered, and what you should now be able to explain in an interview.

## 3. Definition of Done for a checkpoint

Every checkpoint has technical, UX and accessibility acceptance criteria (section 11). Technical items: domain logic, validation, authorization, error handling, persistence, migration, tests, logging, observability, UI states (where UI exists), documentation, security consideration. For LLM features also: versioned prompt and schema, model id stored, token accounting, failure handling, evaluation fixture, grounding strategy, regression test, cost measurement. For agentic features also: explicit state, tool definitions, permission boundaries, termination condition, iteration budget, checkpointing, resume behavior, failure recovery, traceability, human escalation.

## 4. Phase 0: Design and Architecture (documentation only)

Output: this `docs/` folder. It is an implementation-ready specification: requirements with IDs, data model, component register, agent spec, threat model, ADRs, the Product UX + Design System Specification (UX principles, information architecture, navigation, journeys, route inventory, wireframes, state catalog, AI UX patterns, tokens and components), economics, operations plan, and roadmap. Exit: you review and approve, then tag v0.0.1.

## 5. Phase 1: Foundation and Core Intelligence (v0.1.0)

Goal: sign up, upload a resume, correct the profile, paste a job description, receive a grounded requirement-by-requirement analysis in the real UI with a plan for closing the gaps, with run tracing and a seed evaluation set.

| CP | Build | You learn |
|---|---|---|
| 1.1 | Repo skeleton, uv workspace, Docker Compose (postgres, api, web, mailpit), Alembic, fail-fast config, import-linter, CI with real Postgres, secret scanning | Containers, migrations, twelve-factor config, module boundaries |
| 1.2 | **Authentication, authorization, multi-tenancy, isolation tests.** Argon2id, cookie sessions, CSRF, invite signup, repository scoping, RLS, 404 semantics, isolation tests including raw SQL | MVCC, transactions, SET LOCAL and pooling, password hashing, cookies, why RLS |
| 1.3 | **Rate limiting and security boundaries.** Policy-driven limits, security headers, input limits, audit events. Email verification, reset and recovery flows built behind `EMAIL_VERIFICATION_REQUIRED` (off in dev), exercised through Mailpit | Abuse prevention, token design, defense in depth |
| 1.4 | **Task queue plus observability baseline.** Postgres queue, idempotency, retries, dead letters, worker. run_id, workflow_runs and steps, llm_calls with versions, tokens and cost, structured logs, minimal run view. Admin foundation. Mail on the queue. First runbooks | At-least-once delivery, SKIP LOCKED, backoff and jitter, minimum viable observability |
| 1.5 | Visual prototypes of the two critical screens first (opportunities workbench, job detail). Then the design system: tokens, light, dark and system themes, self-hosted fonts, primitives, axe checks in CI | Design tokens, accessibility, contrast computation |
| 1.6 | Resume upload (PDF and DOCX) with validation and private file storage. Parsing in the worker (L) with grounding. Editable profile entries with provenance. Preferences | Untrusted file handling, structured outputs, grounding |
| 1.7 | Evidence chunks, embeddings, pgvector, hybrid retrieval (full-text plus vector, reciprocal rank fusion) | Embeddings, FTS, hybrid ranking |
| 1.8 | Paste a job, canonical JobPosting, requirement extraction (L) with verbatim quotes and a content-hash cache, deterministic eligibility engine, extraction fixtures | Structured outputs, prompt injection, deterministic gates |
| 1.9 | Evidence resolution agent (LangGraph spike decides the implementation, ADR-0004), human escalation with checkpoint and resume, scoring and recommendation, the trust screen, **gap-to-qualify plan**, **verdict feedback labels**, seed evaluation set, regression tests | Agent control flow, checkpointing, deterministic scoring, evaluation basics |

Exit: critical test passes (start analysis, interrupt, kill worker, restart, answer, resume, complete). Isolation tests green. A developer can answer "why this recommendation, which model, which tokens, what cost, which evidence" from stored data. A user can see what is missing for a near-miss job and what would close the gap.

## 6. Phase 2: Resume Studio, Discovery and User Workflow (v0.2.0)

| CP | Build | You learn |
|---|---|---|
| 2.1 | **Resume studio core.** Structured editor with live preview, rich text, lines, spacing, fonts, section order. Professional PDF export (spike and ADR-0025 first). First three templates. Free-plan shape: one resume, rate limited | Rich text editing models, print CSS, PDF rendering |
| 2.2 | **Free canvas editor.** Canva-level freedom, kept professional: every element (name, headline, contacts, sections, items, lines, shapes) is a box on the page that can be dragged, resized, nudged with the arrow keys, snapped to guides, aligned, distributed, layered, multi-selected, locked and grouped, with undo and redo, zoom and a margin grid. Text is edited directly on the page, and the side panel edits the same data, with both updating instantly because the page is drawn in the browser from local state. First step is a **fidelity spike** (browser canvas against the PDF engine) that may reverse the WeasyPrint choice of ADR-0025. Reading order for the PDF and ATS (top to bottom, then left to right), an ATS-safety warning when elements sit in columns or overlap, autosave and versions as in 2.1, structured mode kept for ATS-safe resumes. Images are out of the first version (ADR-0034) | Canvas editors, hit testing, snapping, command history for undo and redo, layout fidelity between a browser and a PDF engine |
| 2.3 | **Template library (24), links, more fonts and color themes, built on the canvas.** One layout engine and 24 template specs, a gallery with previews of your own words, Change template without losing words, an ATS-safe label that is measured, links in text and contacts (https, mailto, tel only), nine font families in twelve pairs, twelve color palettes | Design systems for documents, ATS parsing behavior, URL scheme allowlists |
| 2.4 | **Resume tailoring** (W) with a deterministic grounding check: only confirmed requirements and cited evidence are used, every number, name and job keyword in a suggestion must be found in the old wording or the cited evidence, side by side diff with reason and evidence, accept (re-checked), reject, edit (re-checked), restore point on accept | Claim-level verification, why LLM judges are not enough |
| 2.5 | **Source verification first.** Source registry as a first-class component with all fields in search-requirements.md, company registry, search intent parsing (L), deterministic resolver. Official terms of every candidate source read and recorded before any adapter work | Capability modeling, resolver design, compliance as data |
| 2.6 | Adapters for the sources that pass verification, fetch layer with rate limits, polling intervals, circuit breakers, source health. Provider docs and compliance records completed per source first | Adapter pattern, API compliance, circuit breakers |
| 2.7 | Deduplication with reversible links, private versus public visibility, sightings | Layered matching, data integrity |
| 2.8 | CSV and XLSX import, URL import, SSRF-hardened fetch layer, paste, manual entry, import reports | SSRF, DNS rebinding, untrusted file parsing |
| 2.9 | Opportunities workbench: table, filters (remote, hybrid, location, salary, seniority, employment type, company, source), saved views, keyboard flow, actions (save, dismiss, approve for prep, open original, mark applied), applications tracking, match state machine | Split state machines, TanStack Table, accessibility |
| 2.10 | **Periodic shortlist email** (deterministic selection, templates, per-user schedule), **application text drafts** (cover note, answers to common questions, grounded in evidence, labelled as drafts), tracker polish | Scheduled workflows, grounded generation, notification design |
| 2.11 | **Images, photos and icons on the canvas.** Upload with type and size checks, re-encoding and metadata removal, private storage, crop and fit, an icon set, and PDF output that embeds them. ATS-safe templates stay text only | Untrusted image handling, EXIF removal, file storage |
| 2.12 | **Touch and phone editing.** Pointer and touch gestures for select, move, resize and edit, a mobile layout for the canvas, larger targets, and the same keyboard and screen reader support | Touch events, gesture design, responsive editors |
| 2.13 | **Saved themes and brand kit.** Save a set of fonts and colors for reuse across resumes, a per-user library, apply and update | Per-user settings, row level security for a new table |

Exit: the resume studio produces professional PDFs. Search by role, company, source, location returns real postings from verified sources with honest labeling. Import from unsupported platforms works. Full decision loop to "marked applied". A user receives a shortlist email and can draft application text.

## 7. Phase 3: Intelligence, Monetization and Production (v0.3.0)

| CP | Build | You learn |
|---|---|---|
| 3.1 | GitHub connector (OAuth, least scope, encrypted tokens) and profile enrichment, repo evidence in the agent, restricted-platform user-provided evidence paths | OAuth, scope minimization, untrusted repo content |
| 3.2 | Career Preparation module with all structured actions, gap analysis deepening, plan, mock interview, company research, outreach and referral drafts (the user sends them) | Reusing services instead of adding agents, grounded generation |
| 3.3 | Plans, entitlements, quotas, usage ledger, structured QUOTA_EXCEEDED errors, usage display, free-plan limits (one resume, rate limits). A payment provider interface exists but stays disabled until a provider is chosen and its terms verified | Entitlement design, fair-use architecture |
| 3.4 | Server-side CSV, XLSX and DOCX exports (resume PDF export already exists from 2.1) | Report generation, formula injection |
| 3.5 | Full observability: Run Inspector, Admin Console, source health, cost analytics, dead-letter inspection, alerts | Observability that answers operational questions |
| 3.6 | Full evaluation harness, labeled dataset of about 100 jobs, labeling guidelines, thresholds, history. Evaluate the collected feedback labels and decide on a learned ranker (ADR-0026) | Measuring AI systems |
| 3.7 | Security hardening, production Compose, secrets management, paid LLM tier with no-training terms, backups and restore drill, deployment and rollback, health and readiness, failure drills, incident response, deletion workflow test, email infrastructure, legal review of privacy and terms, remaining runbooks | Running a system, disaster recovery |

Exit: the Definition of Done in the product brief is true, and the go-live gates in business-model.md are checked.

## 8. Production operations coverage map

| Topic | Where |
|---|---|
| Docker and Compose, evolution to production | 1.1, 3.7, production-operations.md |
| Production configuration, secrets | 1.1, 3.7 |
| Backups, restore testing, disaster recovery | 3.7 |
| Migrations, rollback | 1.1, 3.7 |
| Health, readiness, liveness | 1.1, 3.7 |
| Worker recovery, retries, dead letters | 1.4 |
| Source circuit breakers | 2.6 |
| Rate limiting, quotas, abuse prevention | 1.3, 3.3 |
| Structured logging, tracing, token and cost accounting | 1.4, 3.5 |
| Monitoring, alerting | 3.5, 3.7 |
| Deployment, rollback | 3.7 |
| Runbooks, incident response | runbook-index.md |
| Data and account deletion, privacy | 3.7, privacy.md |

## 9. Prioritization when requirements conflict

Security, correctness, user trust, data integrity, explainability, maintainability, reliability, performance, cost, convenience.


## 10. UX as a first-class workstream

UX is built progressively inside the existing checkpoints. There is no separate UI phase. The experience specification is [ux-specification.md](../product/ux-specification.md) and [ai-ux-patterns.md](../product/ai-ux-patterns.md).

### 10.1 Checkpoint definition format

Every checkpoint is written and reviewed in this structure:

| Section | Content |
|---|---|
| Build | What is implemented technically and in the UI |
| UX | What user experience is introduced or changed |
| Technical acceptance criteria | What must work technically |
| UX acceptance criteria | What a user must be able to accomplish and understand |
| Accessibility acceptance criteria | Keyboard, focus, semantics, contrast, screen reader, responsive behavior |
| Test | Backend, frontend, integration and end-to-end tests as appropriate |
| Document | Architecture, ADR and design documentation updates |
| Commit | One coherent commit |
| Interview defense | What you should now be able to explain |

### 10.2 UX by checkpoint

| Checkpoint | UX introduced |
|---|---|
| 1.1 | Application shell, navigation and routing structure, responsive layout strategy, accessibility baseline, frontend folder structure and boundaries, minimum tokens. No product screens |
| 1.2 | Sign-up, sign-in, session states, validation, error handling, expired-session behavior, accessible forms, keyboard flow, mobile layout |
| 1.3 | Rate-limit feedback and security messages. Verification, reset and recovery screens, built behind `EMAIL_VERIFICATION_REQUIRED` |
| 1.4 | The long-running operation state model shared by backend and frontend (queued, processing, retrying, retry available, completed, permanently failed). Minimal Runs list. Admin console |
| 1.5 | Visual prototypes of the two critical screens first. Then the design system implementation: tokens, type, spacing, density, components, form controls, feedback states. Responsive behavior |
| 1.6 | Resume upload, parse status, editable profile, provenance display, preferences |
| 1.7 | Evidence display and the way retrieval results are shown to the user |
| 1.8 | Paste a job, extraction progress, grounding warnings, eligibility gates shown in words |
| 1.9 | **Core UX milestone.** Job analysis experience: overview, requirement-by-requirement analysis, evidence, missing evidence, confidence, score explanation, detail pane, fact versus inference versus suggestion, gap-to-qualify plan, "was this right?" feedback, loading, partial and error states |
| 2.1 | Resume studio: editor ergonomics, live preview, rich text, lines and spacing, fonts, PDF export, save states |
| 2.2 | Canvas editing: selection, handles, snapping guides, keyboard moves, on-page text editing, layers, undo and redo, zoom, the ATS warning, touch and small-screen behavior |
| 2.3 | Template gallery with previews of your own words, ATS-safe labels, Change template, color themes, link editing |
| 2.4 | Tailoring designed around human review: proposed changes, reasons, editing, claim verification, unsupported claims, approve and reject, error recovery |
| 2.5 | Discovery and source attribution |
| 2.6 | Source health and fetch status as users see them |
| 2.7 | Duplicate opportunities, reversible links, private and public postings, source provenance |
| 2.8 | Import workflow: URL, CSV and XLSX, validation, preview, errors, security rejection messages, retry and correction |
| 2.9 | Opportunities workbench as a major feature: table, filters, sorting, search, keyboard navigation, save, dismiss, approve, applied tracking, bulk actions, state transitions, empty, loading and error states |
| 2.10 | Shortlist email design and preferences, application draft editor with clear draft labelling |
| 2.11 | Image upload and crop, icon picker, image rejection messages |
| 2.12 | Touch gestures, mobile canvas layout, target sizes |
| 2.13 | Saving, naming and applying a theme |
| 3.1 | GitHub connection: permission explanation, authorization, connected state, disconnect, scope transparency, failure and retry |
| 3.2 | Career preparation reuses the existing interaction language and pipeline patterns |
| 3.3 | Plan, usage, remaining quota, limits, upgrade state if applicable |
| 3.4 | Export progress, success and failure |
| 3.5 | Run Inspector and admin console: run status, stages, errors, evidence, cost, diagnostics designed around operational questions |
| 3.6 | Evaluation views: dataset and run selection, results, regression visibility, comparison, failure inspection |
| 3.7 | Production UX hardening: accessibility, responsive, error, loading and empty state reviews, security feedback, failure recovery, smoke tests, cross-browser checks |

## 11. Definition of UI/UX done

"UI/UX complete" never means "the page looks good". It means the experience is understandable, consistent, accessible, responsive, state-complete, explainable, recoverable when something fails, consistent with the domain and state model, appropriate for an AI-assisted workflow, and grounded in evidence wherever the product makes an AI claim.

At 1.6 specifically, a user must be able to see what the requirement is, whether they meet it, what evidence supports the conclusion, how confident the system is, why the score was produced, what is missing, and what to do next, without logs, prompts, model output, database records or developer tools.

## 12. Next step

Checkpoint 1.4 is merged. Checkpoint 1.5 is next. Its plan, with questions, is presented for approval before any building starts. The checkpoint document is [checkpoints/checkpoint-1.4.md](../checkpoints/checkpoint-1.4.md) for the latest finished work.

## 13. Revision history

| Revision | Date | Change | Reason |
|---|---|---|---|
| 1 | Phase 0 | Original 19-checkpoint roadmap | Phase 0 planning |
| 2 | 2026-10-30 | 25 checkpoints. Phase 1 gains 1.7 to 1.9 (the old 1.5 and 1.6 are split). Phase 2 is renamed and gains a resume studio (2.1 to 2.4), periodic shortlist email and application drafts (2.10). Source verification is an explicit first step (2.5). Gap-to-qualify plan, feedback labels and outreach drafts added. Paid services are placeholders until later | Competitor review and owner decisions: build the full product in sequence, resume builder with free single resume, better help for finding and applying. See ADR-0027 |
| 3 | 2026-11-01 | 26 checkpoints. New checkpoint 2.2 (free canvas editor). Old 2.2 to 2.9 become 2.3 to 2.10 | Owner decision after testing against Canva-style tools: users must be able to move, resize and edit anything on the page, with instant updates. This is the product gap against other resume builders. See ADR-0034 |
| 4 | 2026-11-01 | 29 checkpoints. New 2.11 (images and icons), 2.12 (touch and phone editing), 2.13 (saved themes). Links in text and more fonts and color sets are part of 2.3 | Owner request after testing 2.2: include images, icons, more fonts, color palettes and saved themes, phone and touch editing, and links. See ADR-0035 |

