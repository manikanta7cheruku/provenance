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

Since checkpoint 1.8 a pasted job description is Tier 2 text that reaches the model. It is wrapped in nonce delimiters, the model's answer is checked by code that keeps only items whose quote is found in the posting ([ADR-0031](../adr/0031-job-paste-extraction-and-eligibility.md)), and eligibility is decided by code from those verified facts. A sentence inside the posting that tells the model what to do can change what is proposed, not what is trusted. Nothing acts without the person's approval.

From checkpoint 1.9 the evidence agent reads a person's own entries and their typed answers, and the requirement text, all treated as data between nonce markers. It has no write tool, no network tool and no way to name another person's rows: evidence is cited by labels that code assigned in the run, and a verdict is accepted only if its quoted words are found in the cited evidence ([ADR-0032](../adr/0032-evidence-agent-and-on-read-scoring.md)). A hostile posting could make the agent give a wrong verdict, but not one that cites something the person does not have.

The resume studio (checkpoint 2.1) takes rich text from the browser and turns it into HTML and a PDF. The browser's JSON is validated against a whitelist on every save and preview, no markup is stored, every string is escaped by one renderer, the preview frame has no scripts, and the PDF engine can read only the shipped fonts. A hostile document can therefore produce odd text but not script, a remote image or a file read ([ADR-0033](../adr/0033-resume-studio-document-and-saving.md)). The free canvas of checkpoint 2.2 adds positions and colors to that data. Both are numbers within the page or a name or a hex code, checked on the server, and each element's CSS is written by the server from those values and escaped for an attribute, so a position or color cannot carry markup or a URL ([ADR-0034](../adr/0034-free-canvas-editor.md)). Links (2.3) are the one place a document can carry an address. The mark accepts only https, http, mailto and tel, refuses whitespace, control characters, quotes and angle brackets, and requires a host for web addresses, on the server and again in the browser. The address is escaped into an `href` with `rel="noopener noreferrer"`, and a `javascript:` or `data:` address is refused with a message next to the text ([ADR-0035](../adr/0035-template-library-links-and-themes.md)).

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
| T7 | Malicious file upload (resume, CSV, XLSX) | Type sniffing not extension only, size caps, parse in worker with resource limits, no macro execution, zip bomb limits, store privately, no inline serving. Resume upload delivered in 1.6 (ADR-0029): raw body, first-byte type check, 5 MB cap enforced while streaming, DOCX read with the standard library and defusedxml (entry, size and ratio limits, no external entities), PDF page and character caps, random storage keys, owner-only attachment download. CSV and XLSX arrive in 2.8 | Fixture tests (unit and integration) |
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
| T22 | A tailored resume that claims something untrue, or text in a job or resume that tries to steer the suggestion model | The model only proposes. Code checks every claim (number, name, tool, job keyword) against the old wording and cited evidence, and a failing suggestion is blocked and cannot be accepted, even after an edit. Accept re-checks against current evidence. Labels assigned by code, so no unknown evidence can be cited. Only confirmed requirements are offered, the rest are marked do not claim. Job, resume and evidence sit between random markers and the prompt says they are data. Names, dates and headings are never offered to the model. Accept is a revision-checked save with a restore point | Verifier tests with invented numbers, tools and employers, integration tests for blocked, forged labels, accept re-check, edit re-check and isolation |

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
