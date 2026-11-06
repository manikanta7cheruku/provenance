# Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [0001](0001-modular-monolith.md) | Modular monolith | Accepted |
| [0002](0002-postgresql-task-queue.md) | PostgreSQL task queue | Accepted, refined by 0022 |
| [0003](0003-pgvector-instead-of-a-separate-vector-database.md) | pgvector instead of a separate vector database | Accepted |
| [0004](0004-langgraph-for-the-agentic-subgraph-pending-spike.md) | LangGraph for the agentic subgraph (pending spike) | Accepted, pending spike |
| [0005](0005-human-approval-boundary.md) | Human approval boundary | Accepted |
| [0006](0006-source-adapter-architecture.md) | Source adapter architecture | Accepted |
| [0007](0007-multi-tenant-data-model.md) | Multi-tenant data model | Accepted |
| [0008](0008-authentication-strategy.md) | Authentication strategy | Accepted |
| [0009](0009-rate-limiting-and-quotas.md) | Rate limiting and quotas | Accepted |
| [0010](0010-free-tier-architecture.md) | Free-tier architecture | Accepted |
| [0011](0011-evidence-grounded-matching.md) | Evidence-grounded matching | Accepted |
| [0012](0012-prompt-injection-threat-model.md) | Prompt-injection threat model | Accepted |
| [0013](0013-visibility-scope-for-private-vs-public-postings.md) | Visibility scope for private vs public postings | Accepted |
| [0014](0014-split-state-machines.md) | Split state machines | Accepted |
| [0015](0015-postgres-rls-as-defense-in-depth.md) | Postgres RLS as defense in depth | Accepted |
| [0016](0016-opaque-sessions-over-jwt.md) | Opaque sessions over JWT | Accepted |
| [0017](0017-one-agent-workflows-for-the-rest.md) | One agent, workflows for the rest | Accepted |
| [0018](0018-development-stack-conventions.md) | Development stack conventions | Accepted |
| [0019](0019-frontend-architecture-and-boundaries.md) | Frontend architecture and boundaries | Accepted |
| [0020](0020-sessions-csrf-and-rate-limiting.md) | Sessions, CSRF protection and rate limiting | Accepted |
| [0021](0021-tenant-isolation-implementation.md) | Tenant isolation implementation | Accepted |
| [0022](0022-queue-semantics-and-system-tables.md) | Queue semantics, payload erasure and system tables | Accepted |
| [0023](0023-admin-scope-and-guards.md) | Administrator scope and guards | Accepted |
| [0024](0024-resume-studio-editor-approach.md) | Resume studio editor approach | Proposed, pending spike |
| [0025](0025-resume-pdf-rendering.md) | Resume PDF rendering | Proposed, pending spike |
| [0026](0026-deterministic-scoring-and-learned-ranker.md) | Deterministic scoring now, learned ranker later | Accepted |
| [0027](0027-build-first-sequencing-and-paid-service-placeholders.md) | Build-first sequencing and paid-service placeholders | Accepted |
| [0028](0028-design-system-implementation.md) | Design system implementation | Accepted |
| [0029](0029-resume-storage-parsing-and-profile-entries.md) | Resume storage, parsing and profile entries | Accepted |
| [0030](0030-evidence-chunks-and-hybrid-retrieval.md) | Evidence chunks and hybrid retrieval | Accepted |
| [0031](0031-job-paste-extraction-and-eligibility.md) | Job paste, grounded requirement extraction and deterministic eligibility | Accepted |
| [0032](0032-evidence-agent-and-on-read-scoring.md) | The evidence agent as a bounded loop in our own code, and scoring computed on read | Accepted |
| [0033](0033-resume-studio-document-and-saving.md) | Resume studio document, saving, versions and exports | Accepted |
| [0034](0034-free-canvas-editor.md) | Free canvas editor | Accepted |
| [0035](0035-template-library-links-and-themes.md) | Template library, links, fonts and color themes | Accepted |
| [0036](0036-resume-tailoring-and-grounding.md) | Resume tailoring with a deterministic grounding check | Accepted |
| [0037](0037-source-registry-and-resolver.md) | Source registry, company registry and a deterministic resolver | Accepted |
| [0038](0038-adapters-fetch-layer-and-circuit-breaker.md) | Source adapters, one fetch layer, and a circuit breaker | Accepted |
| [0039](0039-deduplication-links-and-visibility.md) | Deduplication with reversible links, private and public jobs, and sightings | Accepted |
| [0040](0040-imports-and-the-ssrf-hardened-fetch.md) | Imports (typed, spreadsheet, web page) and the hardened fetch of an address a person typed | Accepted |
| [0041](0041-workbench-decisions-and-server-side-list.md) | The workbench: a decision state machine, a server-side list, and saved views | Accepted |
| [0042](0042-shortlist-email-and-application-drafts.md) | The shortlist email and application drafts | Accepted |
| [0043](0043-pictures-and-icons-on-the-resume.md) | Pictures and icons on the resume | Accepted |
| [0044](0044-touch-and-phone-editing.md) | Touch and phone editing on the canvas | Accepted |
| [0045](0045-saved-themes.md) | Saved themes | Accepted |
| [0046](0046-design-foundation-and-brand.md) | Design foundation and brand | Accepted |
| [0047](0047-the-resume-experience.md) | The resume experience | Accepted |
| [0048](0048-whole-product-polish.md) | Whole-product polish | Accepted |
| [0049](0049-github-connection.md) | The GitHub connection | Accepted |
| [0050](0050-career-preparation.md) | Career preparation | Accepted |
| [0051](0051-plans-entitlements-and-quotas.md) | Plans, entitlements and quotas | Accepted |
| [0052](0052-server-side-reports.md) | Server-side reports (CSV, Excel, Word) | Accepted |
| [0053](0053-observability-and-the-admin-console.md) | Observability, the Run Inspector and the Admin Console | Accepted |

Use [template.md](template.md) for new ADRs. Create an ADR only for meaningful decisions.
