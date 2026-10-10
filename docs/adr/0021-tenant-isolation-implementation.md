# ADR-0021: Tenant isolation implementation

Status: Accepted (checkpoint 1.2). Implements ADR-0007 and ADR-0015.

## Context
Tenant data must stay private even if application code forgets a filter. Administrators must not be able to casually read user data.

## Problem
Decide how the tenant identity reaches the database, which tables are protected by Row Level Security (RLS), and how isolation is proven.

## Options considered
1. Application filters only.
2. RLS driven by a per-transaction setting (`app.user_id`).
3. Separate schema or database per tenant.
4. RLS driven by a database role per user.

## Decision
1. **RLS on every tenant-owned table**, with `ENABLE` and `FORCE`, one policy that both filters reads (`USING`) and restricts writes (`WITH CHECK`). The policy compares `owner_user_id` to `nullif(current_setting('app.user_id', true), '')::uuid`. With no setting the comparison is NULL and no rows are visible (fail closed).
2. **The tenant is set with `set_config('app.user_id', :uid, true)`** at the start of one transaction (`tenant_session` context manager). The third argument makes the value transaction-local, the parameterized equivalent of `SET LOCAL`. It disappears at commit or rollback, so a pooled connection cannot carry one user's identity into the next request.
3. **The identity value comes only from the verified session**, never from request data. The API also filters by owner in every query, so there are two independent layers.
4. **Identity tables are not under RLS** (`users`, `sessions`, `email_tokens`, `invites`, audit and rate limit tables). They are reached before a tenant is known (sign-in, token links) and only through the authentication service by hashed token or email. This is a recorded exception.
5. **No admin bypass.** The policy has no administrator exception. Administrators see aggregates through `/admin/overview` and cannot read tenant rows through the API or the application database role.
6. **The audit log is append-only** for the application role (UPDATE and DELETE are revoked).
7. Isolation is proven by tests at both layers: API tests (404 for every operation, identical responses for foreign and unknown ids, owner cannot be chosen by the client, admin cannot read) and raw SQL as the application role (read filtering, write blocking, fail closed, no leakage across transactions on one connection).

## Why
- Two independent layers mean a single mistake does not expose data.
- Transaction-local settings are safe with connection pooling.
- No admin bypass makes "admins cannot browse private data" a property of the database, not a policy.

## Consequences
- Every tenant table needs the policy and an isolation test. A new tenant table without both is a defect.
- Background workers must set the same context from the task owner before touching tenant data (checkpoint 1.4).
- Queries inside `tenant_session` must not commit mid-way and continue, because the setting would be gone and the next statements would see no rows (a fail-closed failure).
- Break-glass administrator access to tenant data, if ever needed, will be a separate audited mechanism designed in its own ADR.

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Fine |
| 100 | Fine. Indexes start with `owner_user_id` |
| 10,000 | Policy predicates are cheap with the leading index. Consider partitioning large tenant tables by owner |

## Revisit when
A table needs cross-tenant sharing, a customer requires physical isolation, or policy evaluation appears in slow query plans.
