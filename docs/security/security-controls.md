# Security Controls

## Delivered in checkpoints 1.2 and 1.3

Passwords (Argon2id), opaque sessions with rotation and revocation, cookie flags, CSRF token and Origin check, repository scoping plus Row Level Security with FORCE, isolation tests including raw SQL, policy-driven rate limits, security headers, request size limit, append-only audit log, uniform authentication errors, invite-only signup, email verification and reset flows (verification enforced by flag), per-field input limits. See ADR-0020 and ADR-0021.

Not yet delivered: file handling (1.5), untrusted content handling (1.6), SSRF (2.4), export hardening (3.4), connector tokens (3.1), quotas (3.3), backups and incident drills (3.7), dependency vulnerability audit in CI (deferred).

Status: Decided (Phase 0). Each control lists the checkpoint that delivers it.

| Area | Control | Checkpoint |
|---|---|---|
| Configuration | Fail fast on missing or insecure settings in production. No insecure defaults outside dev mode | 1.1 |
| Passwords | Argon2id with parameters tuned and documented | 1.2 |
| Sessions | Opaque token, hash stored, httpOnly Secure SameSite cookie, rotation, revocation | 1.2 |
| CSRF | Token plus Origin check | 1.2 |
| Authorization | Service and repository level scoping, 404 on inaccessible | 1.2 |
| Tenancy | owner_user_id plus RLS FORCE plus non-owner role | 1.2 |
| Isolation tests | Every tenant resource, including raw SQL | 1.2 and each later checkpoint |
| Rate limiting | Policy table driven. Login, registration, reset, upload, URL ingest, analysis, generation, admin | 1.3 |
| Security headers | CSP, HSTS, X-Content-Type-Options, Referrer-Policy, frame protections | 1.3 |
| Input limits | Request size, upload size, field lengths | 1.3 |
| Audit log | Append only audit_events for sensitive actions | 1.3 |
| Logging | Structured, PII-safe, run_id | 1.4 |
| File handling | Private storage, signed URLs, type sniffing, parse limits | 1.5 |
| Untrusted content | Isolation, schema validation, no tools in extraction | 1.6 |
| SSRF | Hardened fetch layer | 2.4 |
| Exports | Formula neutralization | 3.4 |
| Connector tokens | Encryption at rest, least scope | 3.1 |
| Quotas and spend limits | Ledger plus caps | 3.3 |
| Admin capability audit | Explicit capability and audit event | 3.5 |
| Dependency and secret scanning | CI | 1.1 and ongoing |
| Backups and restore | Scheduled, tested | 3.7 |
| Incident response | Runbook and drill | 3.7 |

## Cookie and session settings (specified now, verified in tests)

- Name prefix `__Host-` in production for Secure, Path=/, no Domain attribute.
- httpOnly, Secure, SameSite=Lax (Strict for admin).
- Idle timeout and absolute lifetime configurable.
- Session record keeps a hash of the token and a hash of the user agent, never the token.

## Accepted risk register

Lives in threat-model.md section 6.
