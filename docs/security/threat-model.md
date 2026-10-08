# Threat Model

Status: Decided (Phase 0). Maintained through every phase.

## 1. Assets

| Asset | Sensitivity |
|---|---|
| Resumes, profile, evidence, preferences, work authorization | High personal data |
| Application materials and notes | High |
| Session tokens, password hashes, OAuth tokens, API keys | Critical |
| Job analyses and verdicts | Medium |
| Source and LLM provider credentials, and spend | High (financial) |
| Audit and security logs | Integrity critical |

## 2. Trust tiers

| Tier | Contents | Handling |
|---|---|---|
| 0 | Our code, config, schemas, prompts | Trusted. Reviewed and versioned |
| 1 | Authenticated user input and data | Validated, authorized, isolated per tenant |
| 2 | External content: job descriptions, fetched pages, repository content, CSV cells, company pages, LLM output | Untrusted. Never treated as instructions. Sanitized, size capped, schema checked |

LLM output is Tier 2 until validated by code.

## 3. Actors

External attacker, malicious authenticated user, malicious job poster (controls Tier 2 text), compromised dependency, curious insider or admin, accidental misuse.

## 4. Threats and controls (STRIDE style)

| ID | Threat | Controls | Test |
|---|---|---|---|
| T1 | Cross-tenant read or write (IDOR) | Identity from session only, repository scoping, Postgres RLS with FORCE, non-owner DB role, 404 on miss | Per-resource isolation tests, raw SQL test |
| T2 | Credential stuffing, brute force | Argon2id, per-IP and per-account rate limits, progressive delay and lockout, uniform error text | Rate limit tests, timing comparison |
| T3 | Session theft or fixation | Opaque random tokens, hash stored, httpOnly Secure SameSite cookies, rotation on login and privilege change, revocation on logout and password change | Cookie attribute tests |
| T4 | CSRF | SameSite cookies plus CSRF token on state-changing requests, Origin check | CSRF tests |
| T5 | Prompt injection via job text or repo content | Isolation of untrusted text, no tools in extraction, read-only user-scoped tools for the agent, schema validation, evidence required, length limits, content hash logging, no side effects triggered by content | Injection fixtures in eval and CI |
| T6 | SSRF through URL import, company research, GitHub fetch | Scheme allowlist, DNS resolve then connect to the resolved IP, block loopback, private, link-local, metadata, IPv6 equivalents, recheck each redirect, redirect cap, size and time caps, no cookies or credentials, egress isolation | SSRF suite including DNS rebinding simulation |
| T7 | Malicious file upload (resume, CSV, XLSX) | Type sniffing not extension only, size caps, parse in worker with resource limits, no macro execution, zip bomb limits, store privately, no inline serving | Fixture tests |
| T8 | Stored XSS from job text or profile text | Treat as text, sanitize HTML, strict CSP, escape on render | XSS fixtures |
| T9 | CSV or XLSX formula injection in exports | Neutralize leading formula characters | Export tests |
| T10 | Password reset or verification token abuse | Short lived, single use, hashed at rest, uniform responses | Token tests |
| T11 | Cost abuse (LLM spend) | Quotas, daily caps, global spend ceiling, idempotency, budgets per run, kill switch | Quota and budget tests |
| T12 | Source terms violation | Registry gating, min poll intervals, no bypass features exist in code | Compliance review, registry tests |
| T13 | Secrets leakage | Env or secret manager, never in repo or images, log redaction, secret scanning in CI | CI scan |
| T14 | PII in logs | Structured logging with allowlisted fields, no resume text or full prompts | Log tests |
| T15 | Dependency compromise | Pinned versions, lockfiles, automated vulnerability audit in CI | CI audit |
| T16 | Admin overreach | Admin cannot browse private content without an explicit capability, and every such access creates an audit event | Authorization tests |
| T17 | Unsupported claims reaching a user or employer | Grounding verifier, user approval step, no submission capability | Verifier tests |
| T18 | Race and duplicate execution | Idempotency keys, unique constraints, transactional state transitions | Concurrency tests |
| T19 | Data loss | Backups, restore tests | Restore drills |
| T20 | Account deletion incomplete | Deletion workflow covering DB, object storage, caches, connector tokens | Deletion tests |
| T21 | OAuth token theft | Encrypted at rest, minimal scopes, revocation on disconnect | Connector tests |

## 5. Blast radius analysis for a malicious job description

A posting can contain any text. Even if the model fully obeys it, the extraction call has no tools and returns only a schema validated object. The agent's tools are read only and scoped to the current user. No component can send email, run code, submit applications, or call arbitrary URLs on behalf of content. State transitions are made only by code. Therefore the worst realistic outcome is a wrong or low quality extraction, which evaluation fixtures and evidence requirements are designed to catch.

## 6. Accepted risks (initial)

| Risk | Reason accepted | Revisit |
|---|---|---|
| Free LLM tiers may retain prompts | Test data only during learning | Launch gate: paid no-training tier |
| Single region, single VM at Stage 1 | Cost and simplicity | When uptime requirement is defined |
| Own auth implementation | Learning and control | Reconsider at public signup scale or compliance need |
| Resume parsing errors | Mitigated by user correction | Evaluate |

## 7. Review cadence

Update this document at the end of every checkpoint that adds an entry point, a connector, or a new kind of untrusted input.
