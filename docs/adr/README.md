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

Use [template.md](template.md) for new ADRs. Create an ADR only for meaningful decisions.
