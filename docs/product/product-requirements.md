# Product Requirements

Status: Decided (Phase 0)

## 1. Vision

Provenance answers one question: "Which of these jobs are genuinely worth my time, and why?"

It does this by comparing each job's requirements against the candidate's real evidence and showing the proof. It is a research and decision-support tool. It is not a chatbot, a resume generator, or a scraper.

Positioning line: *Search across connected job sources, authorized integrations, employer career systems, and jobs you provide. Then analyze every opportunity against your actual experience and evidence.*

The product never claims to search a platform it did not search. If a user imports 18 LinkedIn jobs, the product says "Analyzed 18 LinkedIn jobs imported by you."

## 2. Users

| Persona | Need | Success looks like |
|---|---|---|
| Early-career candidate (primary) | Cut through hundreds of postings, know which ones they truly qualify for | Applies to fewer, better jobs and can explain each choice |
| Experienced switcher | Find roles where their evidence maps to a new domain | Sees gaps early and prepares for them |
| Operator (admin) | Keep the system healthy and costs controlled | Answers "why are jobs not appearing" in one screen |

## 3. Primary journey

1. Create an account (invite-only at first) and verify email.
2. Upload a resume. Review and correct the parsed profile.
3. Set preferences and exclusions.
4. Discover jobs from permitted sources, or import jobs (URL, paste, CSV, XLSX).
5. Review ranked opportunities with eligibility and requirement coverage.
6. Open a job, inspect each verdict and its evidence.
7. Save, dismiss, or approve for preparation.
8. Review proposed resume changes. Accept, reject, or edit each. Every claim is verified against evidence.
9. Open the original posting and apply on the employer's site. Mark as applied.

## 4. Functional requirements

IDs are stable. "Phase" is the release in which the requirement is delivered.

### Identity and tenancy
| ID | Requirement | Phase |
|---|---|---|
| FR-AUTH-1 | Email and password sign up with Argon2id hashing | 1 |
| FR-AUTH-2 | Email verification, password reset and recovery supported. Enforced via EMAIL_VERIFICATION_REQUIRED, off in local dev, on in production | 1 (built), 3.7 (deployed) |
| FR-AUTH-3 | Cookie sessions with server-side revocation and logout | 1 |
| FR-AUTH-4 | Password reset with single-use short-lived tokens | 1 |
| FR-AUTH-5 | Rate limits and lockout on auth endpoints | 1 |
| FR-AUTH-6 | Login errors never reveal whether an email exists | 1 |
| FR-TEN-1 | Every tenant row carries owner_user_id and is protected by RLS plus repository scoping | 1 |
| FR-TEN-2 | Inaccessible resources return 404 | 1 |
| FR-TEN-3 | Roles USER and ADMIN. Admin access to private data needs an explicit capability and an audit event | 1 and 3 |

### Profile and evidence
| ID | Requirement | Phase |
|---|---|---|
| FR-PRO-1 | Upload PDF or DOCX resume, parse into structured editable fields | 1 |
| FR-PRO-2 | Every profile entry becomes an evidence chunk with provenance | 1 |
| FR-PRO-3 | User can add evidence by free-text answers | 1 |
| FR-PRO-4 | Preferences: roles, locations, remote, work authorization, sponsorship, compensation, exclusions | 1 |
| FR-EVI-1 | Hybrid retrieval (lexical plus semantic) over evidence | 1 |
| FR-EVI-2 | GitHub connector via OAuth with minimal scopes, repo content as evidence | 3 |

### Jobs and sources
| ID | Requirement | Phase |
|---|---|---|
| FR-JOB-1 | Canonical JobPosting independent of source | 1 |
| FR-JOB-2 | Paste job description | 1 |
| FR-SRC-1 | Source registry with capabilities, compliance status, verification date | 2 |
| FR-SRC-2 | Adapters for permitted sources (see source-compliance.md) | 2 |
| FR-SRC-3 | Resolver returns search, import_required, or unavailable. Never silently substitutes | 2 |
| FR-DUP-1 | Layered deduplication with reversible links | 2 |
| FR-IMP-1 | CSV and XLSX import with column detection and per-row validation report | 2 |
| FR-IMP-2 | URL import with SSRF protection | 2 |
| FR-VIS-1 | Private versus public posting visibility | 1 |

### Analysis
| ID | Requirement | Phase |
|---|---|---|
| FR-EXT-1 | Structured requirement extraction with source spans, schema-validated, cached globally by content hash | 1 |
| FR-ELG-1 | Deterministic four-state eligibility (eligible, not_eligible, uncertain, requires_user_input) | 1 |
| FR-AGT-1 | Evidence Resolution Agent: bounded, checkpointed, interruptible | 1 |
| FR-SCO-1 | Versioned deterministic scoring and recommendation bands, each with reasons | 1 |
| FR-UI-1 | Opportunities workbench: table, filters, detail pane, keyboard flow | 1 basic, 2 full |

### Decision and generation
| ID | Requirement | Phase |
|---|---|---|
| FR-ACT-1 | Actions: save, dismiss, approve for preparation, open original, mark applied | 2 |
| FR-ACT-2 | No application submission state exists anywhere | 2 |
| FR-TAI-1 | Tailored resume bullets, side by side with originals, each claim linked to evidence | 2 |
| FR-TAI-2 | Grounding verifier flags unsupported claims. User accepts, rejects, or edits | 2 |
| FR-PRP-1 | Career preparation module (questions, gaps, roadmap, mock interview) built on existing services | 3 |
| FR-EXP-1 | Server-side CSV, XLSX, PDF, DOCX exports generated from structured data | 3 |

### Operations
| ID | Requirement | Phase |
|---|---|---|
| FR-OPS-1 | Run inspector: why a recommendation happened, which step failed, evidence used, cost, model and prompt version | 3 |
| FR-OPS-2 | Admin console: source health, queue depth, dead letters, usage, security events | 3 |
| FR-OPS-3 | Usage ledger, quotas, plans and entitlements enforced server-side | 3 |
| FR-OPS-4 | Evaluation harness with versioned labeled dataset | 3 |

## 5. Non-functional requirements

| Area | Requirement |
|---|---|
| Security | OWASP ASVS Level 1 as a minimum target. Threat model maintained. No secrets in repo |
| Privacy | Data minimization, deletion flow, PII-safe logs, no public file URLs |
| Reliability | At-least-once task execution with idempotency. Crash recovery proven by test |
| Performance targets | List and filter views under 300 ms server time at closed-cohort scale. Basic discovery 5 to 20 s. Deep analysis shown progressively. Targets to measure, not guarantees |
| Accessibility | WCAG 2.2 AA where practical. Keyboard complete. Reduced-motion support |
| Responsiveness | Desktop, tablet, mobile. Mobile uses dedicated detail screens, not a squeezed split pane |
| Observability | Every workflow has a run_id. Structured logs. No resume text in logs |
| Portability | Whole stack runs from Docker Compose on Windows, macOS, Linux |
| Cost | Global work shared across users. Expensive generation only on explicit request |

## 6. Explicit non-goals

- Automatic application submission or browser automation to apply.
- Scraping or crawling any platform that does not permit it.
- Bypassing authentication, CAPTCHAs, anti-bot systems, or rate limits.
- A general chat assistant as the primary interface.
- Microservices at the start.
- Payment processing in Phases 1 to 3. Plans and quotas exist. Billing does not.

## 7. Success metrics

Measured from real usage. Targets are set after the first cohort, not invented here.

| Metric | Why it matters |
|---|---|
| Jobs analyzed per active user per week | Core engagement |
| Share of recommended jobs the user saves or approves | Recommendation quality |
| False-negative rate on eligibility (eval set) | Wrongly excluding a qualified candidate is the worst error |
| Unsupported verdict rate (eval set) | Trust |
| Unsupported claim rate in tailoring (eval set) | Trust |
| Median time from upload to first analyzed job | Onboarding quality, aim for about six minutes |
| Cost per analyzed job | Sustainability |

## 8. Recommendation bands

Deterministic. Order of evaluation:

1. Hard gate failed: **Not eligible**.
2. Otherwise compute coverage and fit from versioned config: **Strong match**, **Good match**, **Review**, **Not recommended**.

Every band shows reasons: requirements supported out of required total, strengths, gaps, eligibility statement. No unexplained percentages. Any number shown is rounded deliberately.

## 9. Verdict vocabulary

Per requirement: **Met**, **Partial**, **Not verified**, **Conflicting**, **Blocker**.

Per evidence item: **Direct**, **Inferred**, **Missing**, **Conflicting**. The UI never shows an inference as a fact.

## 10. Related specifications

- [User journey](user-journey.md)
- [Search, company and source requirements](search-requirements.md)
- [Career preparation requirements](career-preparation-requirements.md)
- [Export and reporting requirements](export-reporting-requirements.md)
- [AI economics](ai-economics.md)
- [Identity and data lifecycle requirements](../security/identity-and-data-lifecycle-requirements.md)
- [Admin and operational requirements](../operations/admin-operations-requirements.md)
- [Component register](../architecture/component-register.md)
