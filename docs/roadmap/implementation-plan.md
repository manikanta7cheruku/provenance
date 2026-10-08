# Master Implementation Plan

Status: Decided (Phase 0). This is the single roadmap. Amendments from the review of Phase 0 are incorporated here.

## 1. Release phases

| Phase | Name | Tag |
|---|---|---|
| 0 | Design and Architecture | v0.0.1 |
| 1 | Foundation and Core Intelligence | v0.1.0 |
| 2 | Real Job Discovery and User Workflow | v0.2.0 |
| 3 | Intelligence, Monetization and Production | v0.3.0 |

Each phase is cut into checkpoints. Each checkpoint is runnable, tested, documented and committed on its own.

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

Goal: sign up, upload a resume, correct the profile, paste a job description, receive a grounded requirement-by-requirement analysis in the real UI, with run tracing and a seed evaluation set.

| CP | Build | You learn |
|---|---|---|
| 1.1 | Repo skeleton, uv workspace, Docker Compose (postgres, api, web, mailpit), Alembic, fail-fast config, import-linter, CI with real Postgres, secret scanning | Containers, migrations, twelve-factor config, module boundaries |
| 1.2 | **Authentication, authorization, multi-tenancy, isolation tests.** Argon2id, cookie sessions, CSRF, invite signup, repository scoping, RLS, 404 semantics, isolation tests including raw SQL | MVCC, transactions, SET LOCAL and pooling, password hashing, cookies, why RLS |
| 1.3 | **Rate limiting and security boundaries.** Policy-driven limits, security headers, input limits, audit events. Email verification, reset and recovery flows built behind `EMAIL_VERIFICATION_REQUIRED` (off in dev), exercised through Mailpit | Abuse prevention, token design, defense in depth |
| 1.4 | **Task queue plus observability baseline.** Postgres queue, idempotency, retries, dead letters, worker. run_id, workflow_runs and steps, llm_calls with versions, tokens and cost, structured logs, minimal run view. First runbooks | At-least-once delivery, SKIP LOCKED, backoff and jitter, minimum viable observability |
| 1.5 | Design system and app shell, resume upload and parsing (L), editable profile, evidence chunks, embeddings, pgvector, hybrid retrieval | Embeddings, FTS, hybrid ranking, design tokens, accessibility |
| 1.6 | JD paste and canonical JobPosting, requirement extraction (L) with global cache, eligibility, LangGraph spike then evidence agent, human escalation with checkpoint and resume, scoring and recommendation, detail pane with evidence drill-down. **Seed evaluation set, versioned prompts and models, regression tests, grounding and schema failure records** | Structured outputs, prompt injection, agent control flow, checkpointing, deterministic scoring, evaluation basics |

Exit: critical test passes (start analysis, interrupt, kill worker, restart, answer, resume, complete). Isolation tests green. A developer can answer "why this recommendation, which model, which tokens, what cost, which evidence" from stored data.

## 6. Phase 2: Real Job Discovery and User Workflow (v0.2.0)

| CP | Build | You learn |
|---|---|---|
| 2.1 | **Source registry as a first-class component** with all fields in search-requirements.md, company registry, search intent parsing (L), deterministic resolver, company and source as first-class filters, progress counters | Capability modeling, resolver design, compliance as data |
| 2.2 | Adapters for verified sources (Greenhouse, Lever, Ashby, Remotive, Adzuna as verified), fetch layer with rate limits, polling intervals, circuit breakers, source health. Provider docs and compliance records completed per source first | Adapter pattern, API compliance, circuit breakers |
| 2.3 | Deduplication with reversible links, private versus public visibility, sightings | Layered matching, data integrity |
| 2.4 | CSV and XLSX import, URL import, SSRF-hardened fetch layer, paste, manual entry, import reports | SSRF, DNS rebinding, untrusted file parsing |
| 2.5 | Opportunities workbench: table, filters, saved views, keyboard flow, actions (save, dismiss, approve for prep, open original, mark applied), applications tracking, match state machine | Split state machines, TanStack Table, accessibility |
| 2.6 | Resume tailoring (W) and grounding verifier, side by side diff, accept, reject, edit | Claim-level verification, why LLM judges are not enough |

Exit: search by role, company, source, location returns real postings from verified sources with honest labeling. Import from unsupported platforms works. Full decision loop to "marked applied".

## 7. Phase 3: Intelligence, Monetization and Production (v0.3.0)

| CP | Build | You learn |
|---|---|---|
| 3.1 | GitHub connector (OAuth, least scope, encrypted tokens) and profile enrichment, repo evidence in the agent, restricted-platform user-provided evidence paths | OAuth, scope minimization, untrusted repo content |
| 3.2 | Career Preparation module with all structured actions, gap analysis, plan, mock interview, company research | Reusing services instead of adding agents, grounded generation |
| 3.3 | Plans, entitlements, quotas, usage ledger, structured QUOTA_EXCEEDED errors, usage display | Entitlement design, fair-use architecture |
| 3.4 | Server-side CSV, XLSX, PDF, DOCX exports | Report generation, formula injection |
| 3.5 | Full observability: Run Inspector, Admin Console, source health, cost analytics, dead-letter inspection, alerts | Observability that answers operational questions |
| 3.6 | Full evaluation harness, labeled dataset of about 100 jobs, labeling guidelines, thresholds, history | Measuring AI systems |
| 3.7 | Security hardening, production Compose, secrets management, backups and restore drill, deployment and rollback, health and readiness, failure drills, incident response, deletion workflow test, email infrastructure, remaining runbooks | Running a system, disaster recovery |

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
| Source circuit breakers | 2.2 |
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

The UX amendment numbered checkpoints against a shorter roadmap. It is mapped here by content to the approved numbering. No checkpoint was added, removed or reordered.

| Checkpoint | UX introduced |
|---|---|
| 1.1 | Application shell, navigation and routing structure, responsive layout strategy, accessibility baseline, frontend folder structure and boundaries, minimum tokens. No product screens |
| 1.2 | Sign-up, sign-in, session states, validation, error handling, expired-session behavior, accessible forms, keyboard flow, mobile layout |
| 1.3 | Rate-limit feedback and security messages. Verification, reset and recovery screens, built behind `EMAIL_VERIFICATION_REQUIRED` |
| 1.4 | The long-running operation state model shared by backend and frontend (queued, processing, retrying, retry available, completed, permanently failed). Minimal Runs list |
| 1.5 | Visual prototypes of the two critical screens first. Then the design system implementation: tokens, type, spacing, density, components, form controls, feedback states. Resume upload, parse status, editable profile, evidence display with provenance. Responsive behavior |
| 1.6 | **Core UX milestone.** Job analysis experience: overview, requirement-by-requirement analysis, evidence, missing evidence, confidence, score explanation, detail pane, fact versus inference versus suggestion, available actions, loading, partial and error states |
| 2.1 | Discovery and source attribution |
| 2.3 | Duplicate opportunities, reversible links, private and public postings, source provenance |
| 2.4 | Import workflow: URL, CSV and XLSX, validation, preview, errors, security rejection messages, retry and correction |
| 2.5 | Opportunities workbench as a major feature: table, filters, sorting, search, keyboard navigation, save, dismiss, approve, applied tracking, bulk actions, state transitions, empty, loading and error states |
| 2.6 | Tailoring designed around human review: proposed changes, reasons, editing, claim verification, unsupported claims, approve and reject, error recovery |
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

Checkpoint 1.1 is documented in [checkpoints/checkpoint-1.1.md](../checkpoints/checkpoint-1.1.md). Checkpoint 1.2 follows when 1.1 is verified on your machine.
