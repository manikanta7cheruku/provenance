# ADR-0023: Administrator scope and guards

Status: Accepted (checkpoint 1.4). Builds on [ADR-0015](0015-postgres-rls-as-defense-in-depth.md), [ADR-0016](0016-opaque-sessions-over-jwt.md) and [ADR-0021](0021-tenant-isolation-implementation.md).

## Context
Someone has to create invites, disable abusive accounts, requeue stuck work and see whether the system is healthy. An administrator role is the usual answer and the usual source of privacy failures.

## Problem
How do administrators operate the system without being able to read what users store, and without being able to lock the system out of administration?

## Options considered
| Option | Result |
|---|---|
| Admin role that bypasses RLS and sees everything | Convenient, but one stolen admin session exposes every resume. Rejected. |
| No admin tooling, operate through SQL | Error prone, unaudited. Rejected. |
| Admin console limited to accounts, counters, queue state and audit, with guards | Chosen. |

## Decision
1. **The server decides.** Every admin endpoint depends on `require_admin`. Non-admins receive 404, as if the area did not exist. The frontend hides the screens as a convenience only. A mutation also needs a valid CSRF token and writes an audit event with actor, action and target.
2. **Admins see metadata and counters.** They never see resumes, profile entries, evidence or jobs. RLS has no admin exception and the admin services never query tenant tables. Per-user numbers come from `user_stats`, which database triggers keep up to date. Tests insert a marker into a user's profile and assert it appears in no admin response.
3. **Guards.** An admin cannot disable their own account. The last active admin cannot be demoted or disabled. The check locks the admin rows (`FOR UPDATE`) so two simultaneous demotions cannot both succeed.
4. **Disabling revokes sessions.** `is_active=false` is checked on every request in `resolve_session`, and existing sessions are revoked as well.
5. **Invites** are created in the console and shown once. Only a hash is stored. They can be bound to an email and revoked. Revoked invites cannot register.
6. **Dead letters** can be requeued only when the task type allows it (ADR-0022).
7. **Plans and limits** appear only after checkpoint 3.3.

## Why
Operational needs are met by metadata. Keeping content out of reach is a property of the data model (no bypass role, no content in admin queries), not of a promise in code.

## Consequences
- Supporting a user cannot involve looking at their data. Support goes through the user, or through a future explicit break-glass capability with a stated reason and audit event (not built).
- The admin console is read-heavy and small. Anything that needs content stays out of it by design.

## Revisit when
Support volume demands break-glass access. That needs its own ADR with a reason prompt, time limit and user-visible audit record.
