# Identity, Authorization, Abuse Prevention and Data Lifecycle Requirements

Status: Decided (Phase 0)

## 1. Build order (Phase 1)

```
Authentication -> Authorization -> Multi-tenancy -> Tenant isolation tests -> Rate limiting -> Security boundaries
```

## 2. Authentication

| Requirement | Detail |
|---|---|
| Method | Email and password |
| Hashing | Argon2id. Parameters documented and revisited as hardware changes |
| Sessions | Opaque tokens in cookies. Server-side record. Logout revokes. Password change revokes all other sessions |
| Uniform errors | Same message and similar timing for unknown email and wrong password |
| Provider seam | An AuthProvider interface so a managed identity provider can be substituted without touching domain authorization |
| Invite-only | Signup requires an invite code in early stages. Public signup is a configuration switch |

### Email verification and recovery: supported by architecture, not blocking local development

| Mode | Behavior |
|---|---|
| `EMAIL_VERIFICATION_REQUIRED=false` (default in local dev) | Accounts are usable immediately. Verification and reset flows exist and can be exercised through Mailpit |
| `EMAIL_VERIFICATION_REQUIRED=true` (production) | Sensitive actions blocked until verified: connecting GitHub, exports, sharing, deleting account via email confirmation, and any paid feature |

The flows (verification, password reset, email change, account recovery) are designed now: tokens are single use, short lived, stored hashed, rate limited. Mail goes through a mail interface with an SMTP implementation. Delivery infrastructure (domain, SPF, DKIM, provider account) is a deployment task in checkpoint 3.7 and must not delay core features. Production refuses to start with verification required but no mail transport configured.

## 3. Authorization

- Authenticated identity is the only source of ownership. Client supplied user ids are ignored.
- Checks at service and repository layers. Routes are not the only gate.
- 404 for resources that exist but are not accessible.
- Roles: USER, ADMIN. Admin sees operational data. Private user content needs an explicit capability and an audit event.
- Future shape: User to Organization to Membership to Role to Resource. Not built now.

## 4. Multi-tenancy

Every tenant row has owner_user_id. RLS on. DB role without BYPASSRLS. Workers set tenant context from the task owner. Cross-tenant tests are required for every resource and every CRUD path.

## 5. Rate limiting

Policies are configuration rows, evaluated by a RateLimitPolicy service backed by Postgres counters at Stage 1 (migrate to an in-memory or Redis counter only on measured need, ADR-0009).

| Endpoint class | Example starting policy (configurable) |
|---|---|
| Login | 5 per minute per IP, plus per-account throttle |
| Registration | Low per IP per hour |
| Password reset | 3 per hour per account |
| Resume upload | 10 per hour per user |
| URL ingestion | 20 per hour per user |
| Analysis and generation | Per-user quotas via ledger, plus burst limits |
| Admin | Separate limits |
| Reads (list, filter, detail) | Generous |

Exceeded limits return a structured error with retry timing.

## 6. Abuse prevention

Rate limits, quotas, invite gating, per-user daily caps, upload and URL restrictions, global spend ceiling, duplicate suppression, suspicious content logging (content hashes, injection indicators), account suspension capability for admins with audit, disposable-email handling decided before public signup.

## 7. Data deletion and account deletion

| Item | Requirement |
|---|---|
| User triggered account deletion | Confirmation step, then a durable deletion workflow |
| Scope | Profile, resumes and versions, evidence and embeddings, preferences, sightings, matches, verdicts, materials, feedback, usage events (anonymized or retained only as legally required), sessions, connector tokens, exports, object storage files |
| Shared global data | Postings and analyses derived from public sources remain. Private postings of the user are deleted |
| Backups | Deleted data persists in backups until backup expiry. The retention window is documented in privacy.md |
| Verification | A deletion test confirms zero rows with the user's id remain in tenant tables and objects are gone |
| Audit | A minimal non-personal deletion record is kept |
| Data export | User can export their data before deletion |

## 8. Backup and recovery

| Item | Requirement |
|---|---|
| Database backups | Scheduled logical backups and, where the host supports it, point-in-time recovery. Frequency set from tolerated data loss (RPO) |
| Object storage | Versioning or replicated copy for resumes and exports |
| Restore testing | A restore drill is performed and timed before launch and repeated on schedule |
| Targets | RPO and RTO are defined before launch and recorded in operations docs. They are decisions to make with real requirements, not guessed here |
| Secrets | Recovery of the encryption key is part of the plan. Losing it makes connector tokens unrecoverable by design |
| Disaster recovery | Documented procedure to rebuild from backups on a fresh host |

## 9. Acceptance criteria

1. Unknown email and wrong password return identical responses.
2. A session cookie after logout is rejected.
3. Isolation tests pass for each resource.
4. Rate limits trigger and return structured errors.
5. With verification flag on, sensitive actions are blocked until verified. With it off, the same flows are testable via Mailpit.
6. Account deletion test passes.
7. Restore drill succeeds.
